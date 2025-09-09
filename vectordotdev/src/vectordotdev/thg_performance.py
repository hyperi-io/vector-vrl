"""
THG (Throughput) Performance Assessment for Vector Processing
Measures and analyzes Vector pipeline performance with real-time metrics
"""

import time
import json
import statistics
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from pathlib import Path
import subprocess
import tempfile

from .vector_test_utils import VectorTestRunner


@dataclass
class THGMetrics:
    """Throughput metrics for Vector performance assessment"""
    events_per_second: float
    bytes_per_second: float
    latency_p50: float
    latency_p95: float
    latency_p99: float
    memory_usage_mb: float
    cpu_usage_percent: float
    total_events_processed: int
    total_bytes_processed: int
    processing_time_seconds: float
    error_rate_percent: float = 0.0


@dataclass  
class THGResult:
    """Complete THG assessment result"""
    pattern_name: str
    vrl_code: str
    metrics: THGMetrics
    thg_score: float  # Overall THG performance score (0-1000+)
    performance_grade: str  # A+, A, B, C, D, F
    recommendations: List[str]
    raw_output: List[Dict[str, Any]]


class THGPerformanceAssessor:
    """
    Assess Vector processing performance with THG scoring
    Measures real Vector performance with production-like loads
    """
    
    def __init__(self, vector_binary: str = "/usr/bin/vector"):
        self.vector_runner = VectorTestRunner(vector_binary)
        self.temp_dir = Path("/projects/vectordotdev/.tmp")  # Use project temp dir
        
        # THG scoring thresholds (events/second)
        self.thg_grades = {
            1000: "A+",  # Excellent (1K+ eps)
            500: "A",    # Very Good (500+ eps)
            250: "B",    # Good (250+ eps)
            100: "C",    # Acceptable (100+ eps)
            50: "D",     # Below Target (50+ eps)
            0: "F"       # Needs Optimization
        }
    
    def assess_pattern_performance(self, pattern_name: str, vrl_code: str, 
                                 test_logs: List[str], iterations: int = 100) -> THGResult:
        """
        Assess THG performance for a specific VRL pattern
        """
        print(f"🔥 THG Assessment: {pattern_name}")
        print(f"📊 Processing {len(test_logs)} sample logs × {iterations} iterations")
        
        # Prepare test data
        all_test_logs = test_logs * iterations
        
        # Execute performance test
        start_time = time.time()
        success, results, error_msg = self.vector_runner.test_vrl_with_vector(
            vrl_code, all_test_logs, f"thg_{pattern_name}"
        )
        end_time = time.time()
        
        processing_time = end_time - start_time
        total_events = len(all_test_logs)
        total_bytes = sum(len(log.encode('utf-8')) for log in all_test_logs)
        
        if not success:
            return THGResult(
                pattern_name=pattern_name,
                vrl_code=vrl_code,
                metrics=THGMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, processing_time, 100.0),
                thg_score=0.0,
                performance_grade="F",
                recommendations=[f"VRL compilation failed: {error_msg}"],
                raw_output=[]
            )
        
        # Calculate basic metrics
        events_per_second = total_events / processing_time if processing_time > 0 else 0
        bytes_per_second = total_bytes / processing_time if processing_time > 0 else 0
        
        # Calculate latencies (estimate based on batch processing)
        estimated_latency = (processing_time / total_events) * 1000 if total_events > 0 else 0  # ms
        latency_p50 = estimated_latency
        latency_p95 = estimated_latency * 1.5  # Conservative estimate
        latency_p99 = estimated_latency * 2.0  # Conservative estimate
        
        # Estimate resource usage (basic approximation)
        memory_usage = min(100, total_bytes / (1024 * 1024) * 0.1)  # Rough estimate
        cpu_usage = min(100, events_per_second / 10)  # Rough estimate based on throughput
        
        # Error rate calculation
        successful_events = len([r for r in results if r])
        error_rate = ((total_events - successful_events) / total_events) * 100 if total_events > 0 else 0
        
        metrics = THGMetrics(
            events_per_second=events_per_second,
            bytes_per_second=bytes_per_second,
            latency_p50=latency_p50,
            latency_p95=latency_p95,
            latency_p99=latency_p99,
            memory_usage_mb=memory_usage,
            cpu_usage_percent=cpu_usage,
            total_events_processed=successful_events,
            total_bytes_processed=total_bytes,
            processing_time_seconds=processing_time,
            error_rate_percent=error_rate
        )
        
        # Calculate THG score and grade
        thg_score = self._calculate_thg_score(metrics)
        grade = self._get_performance_grade(events_per_second)
        recommendations = self._generate_recommendations(metrics, vrl_code)
        
        return THGResult(
            pattern_name=pattern_name,
            vrl_code=vrl_code,
            metrics=metrics,
            thg_score=thg_score,
            performance_grade=grade,
            recommendations=recommendations,
            raw_output=results
        )
    
    def _calculate_thg_score(self, metrics: THGMetrics) -> float:
        """
        Calculate comprehensive THG score (0-1000+)
        Weighs throughput, latency, and reliability
        """
        # Throughput score (0-800 points)
        throughput_score = min(800, metrics.events_per_second * 0.8)
        
        # Latency score (0-100 points, lower is better)
        latency_penalty = min(100, metrics.latency_p95 / 10)
        latency_score = max(0, 100 - latency_penalty)
        
        # Reliability score (0-100 points)
        reliability_score = max(0, 100 - metrics.error_rate_percent)
        
        # Resource efficiency score (0-100 points)
        memory_penalty = min(50, metrics.memory_usage_mb / 10)
        cpu_penalty = min(50, metrics.cpu_usage_percent / 2)
        efficiency_score = max(0, 100 - memory_penalty - cpu_penalty)
        
        total_score = throughput_score + latency_score + reliability_score + efficiency_score
        return round(total_score, 1)
    
    def _get_performance_grade(self, events_per_second: float) -> str:
        """Get performance grade based on events per second"""
        for threshold, grade in sorted(self.thg_grades.items(), reverse=True):
            if events_per_second >= threshold:
                return grade
        return "F"
    
    def _generate_recommendations(self, metrics: THGMetrics, vrl_code: str) -> List[str]:
        """Generate performance optimization recommendations"""
        recommendations = []
        
        if metrics.events_per_second < 100:
            recommendations.append("🐌 Low throughput - consider using built-in parsers instead of string operations")
        
        if metrics.error_rate_percent > 10:
            recommendations.append("⚠️ High error rate - review VRL null handling and error cases")
        
        if metrics.latency_p95 > 100:
            recommendations.append("🕐 High latency - optimize VRL for sequential processing")
        
        if "split(" in vrl_code and vrl_code.count("split(") > 3:
            recommendations.append("✂️ Multiple splits detected - consider parse_key_value() or parse_json()")
        
        if "to_string(" in vrl_code and vrl_code.count("to_string(") > 5:
            recommendations.append("🔤 Excessive string conversions - cache converted values")
        
        if metrics.memory_usage_mb > 50:
            recommendations.append("💾 High memory usage - review intermediate variable creation")
        
        if not recommendations:
            if metrics.events_per_second >= 350:
                recommendations.append("🚀 Excellent performance - THG target achieved!")
            else:
                recommendations.append("✅ Good performance - consider minor optimizations")
        
        return recommendations
    
    def benchmark_multiple_patterns(self, pattern_configs: List[Dict]) -> List[THGResult]:
        """
        Benchmark multiple patterns and compare performance
        pattern_configs: List of {'name': str, 'vrl': str, 'test_logs': List[str]}
        """
        results = []
        
        print(f"🏁 THG Benchmark: {len(pattern_configs)} patterns")
        print("=" * 60)
        
        for i, config in enumerate(pattern_configs, 1):
            print(f"\n[{i}/{len(pattern_configs)}] Testing: {config['name']}")
            
            result = self.assess_pattern_performance(
                pattern_name=config['name'],
                vrl_code=config['vrl'],
                test_logs=config['test_logs'],
                iterations=50  # Lower for batch testing
            )
            
            results.append(result)
            
            # Print immediate results
            print(f"  THG Score: {result.thg_score:.1f}")
            print(f"  Grade: {result.performance_grade}")  
            print(f"  Throughput: {result.metrics.events_per_second:.1f} eps")
        
        # Print summary
        self._print_benchmark_summary(results)
        return results
    
    def _print_benchmark_summary(self, results: List[THGResult]):
        """Print comprehensive benchmark summary"""
        print("\n" + "=" * 60)
        print("🏆 THG PERFORMANCE SUMMARY")
        print("=" * 60)
        
        # Sort by THG score
        sorted_results = sorted(results, key=lambda r: r.thg_score, reverse=True)
        
        print(f"{'Rank':<4} {'Pattern':<25} {'THG Score':<10} {'Grade':<5} {'EPS':<8}")
        print("-" * 60)
        
        for i, result in enumerate(sorted_results, 1):
            print(f"{i:<4} {result.pattern_name[:24]:<25} "
                  f"{result.thg_score:<10.1f} {result.performance_grade:<5} "
                  f"{result.metrics.events_per_second:<8.1f}")
        
        # Statistics
        scores = [r.thg_score for r in results]
        throughputs = [r.metrics.events_per_second for r in results]
        
        print("\n📊 STATISTICS:")
        print(f"  Average THG Score: {statistics.mean(scores):.1f}")
        print(f"  Median Throughput: {statistics.median(throughputs):.1f} eps")
        print(f"  Top Performance: {max(throughputs):.1f} eps ({sorted_results[0].pattern_name})")
        
        # Performance categories
        excellent = len([r for r in results if r.metrics.events_per_second >= 350])
        good = len([r for r in results if 100 <= r.metrics.events_per_second < 350])
        needs_work = len([r for r in results if r.metrics.events_per_second < 100])
        
        print(f"\n📈 PERFORMANCE DISTRIBUTION:")
        print(f"  🚀 Excellent (350+ eps): {excellent}")
        print(f"  ✅ Good (100-349 eps): {good}")  
        print(f"  ⚠️ Needs Work (<100 eps): {needs_work}")


def quick_thg_assessment(vrl_code: str, test_logs: List[str], pattern_name: str = "test") -> float:
    """
    Quick THG assessment for a single pattern
    Returns THG score for immediate feedback
    """
    assessor = THGPerformanceAssessor()
    result = assessor.assess_pattern_performance(pattern_name, vrl_code, test_logs, iterations=20)
    
    print(f"⚡ Quick THG: {result.thg_score:.1f} ({result.performance_grade}) - {result.metrics.events_per_second:.1f} eps")
    return result.thg_score


if __name__ == "__main__":
    # Example usage
    sample_vrl = '''
    message_str = to_string(.message) ?? ""
    parsed, err = parse_json(message_str)
    if err == null {
        .timestamp = parsed.timestamp
        .level = parsed.level
    }
    '''
    
    sample_logs = [
        '{"timestamp": "2023-01-01T12:00:00Z", "level": "INFO", "message": "Test log"}',
        '{"timestamp": "2023-01-01T12:00:01Z", "level": "ERROR", "message": "Error occurred"}',
    ]
    
    score = quick_thg_assessment(sample_vrl, sample_logs, "json_parser")
    print(f"Final THG Score: {score}")
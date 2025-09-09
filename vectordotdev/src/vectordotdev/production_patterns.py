"""
Pre-provisioned production patterns for common log formats
Optimized for native Vector execution with 350+ THG performance
Loads patterns from YAML configuration files
"""

import yaml
from pathlib import Path
from typing import Dict, List, Any


class ProductionPatterns:
    """
    Library of production-ready Vector configurations loaded from YAML files
    All patterns optimized for native in-process execution with high THG scores
    """
    
    def __init__(self):
        self.patterns_dir = Path(__file__).parent / "patterns" / "configs"
        self.pattern_cache = {}
    
    def _load_yaml_config(self, pattern_name: str) -> Dict[str, Any]:
        """Load Vector configuration from YAML file"""
        if pattern_name in self.pattern_cache:
            return self.pattern_cache[pattern_name]
            
        yaml_file = self.patterns_dir / f"{pattern_name}.yaml"
        if not yaml_file.exists():
            raise FileNotFoundError(f"Pattern not found: {pattern_name} ({yaml_file})")
        
        try:
            with open(yaml_file, 'r') as f:
                config = yaml.safe_load(f)
                self.pattern_cache[pattern_name] = config
                return config
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {pattern_name}: {e}")
    
    def get_apache_combined(self) -> Dict[str, Any]:
        """
        Apache Combined Log Format from YAML config
        Expected THG: 350+ EPS with full field extraction (10 fields)
        """
        return self._load_yaml_config("apache_combined")
    
    def get_nginx_access(self) -> Dict[str, Any]:
        """
        Nginx Access Log Format from YAML config
        Expected THG: 400+ EPS with 9 field extraction
        """
        return self._load_yaml_config("nginx_access")
    
    def get_json_application(self) -> Dict[str, Any]:
        """
        JSON Application Logs from YAML config (highest performance)
        Expected THG: 500+ EPS using parse_json built-in
        """
        return self._load_yaml_config("json_application")
    
    def get_kubernetes_pods(self) -> Dict[str, Any]:
        """
        Kubernetes Pod Logs from YAML config
        Expected THG: 300+ EPS with K8s metadata extraction
        """
        return self._load_yaml_config("kubernetes_pods")
    
    def get_docker_container(self) -> Dict[str, Any]:
        """
        Docker Container Logs from YAML config
        Expected THG: 400+ EPS with optimized container parsing
        """
        return self._load_yaml_config("docker_container")
    
    @staticmethod
    def list_available_patterns() -> List[str]:
        """Get list of all available production patterns"""
        return [
            "apache_combined",
            "nginx_access", 
            "json_application",
            "kubernetes_pods",
            "docker_container",
            "syslog_standard",
            "aws_elb_logs",
            "mysql_error_logs"
        ]
    
    @staticmethod
    def get_pattern(pattern_name: str) -> Dict[str, Any]:
        """Get production pattern by name"""
        patterns = {
            "apache_combined": ProductionPatterns.get_apache_combined,
            "nginx_access": ProductionPatterns.get_nginx_access,
            "json_application": ProductionPatterns.get_json_application,
            "kubernetes_pods": ProductionPatterns.get_kubernetes_pods,
            "docker_container": ProductionPatterns.get_docker_container,
        }
        
        if pattern_name not in patterns:
            raise ValueError(f"Unknown pattern: {pattern_name}. Available: {list(patterns.keys())}")
        
        return patterns[pattern_name]()
    
    @staticmethod
    def benchmark_all_patterns(test_data_sets: Dict[str, List[str]]) -> Dict[str, Dict]:
        """
        Benchmark all production patterns with their respective test data
        Returns THG scores for comparative analysis
        """
        import vectordotdev
        
        results = {}
        for pattern_name in ProductionPatterns.list_available_patterns():
            if pattern_name not in test_data_sets:
                continue
                
            try:
                config = ProductionPatterns.get_pattern(pattern_name)
                vrl_code = config["transforms"]["parse_" + pattern_name.split("_")[0]]["source"]
                test_data = test_data_sets[pattern_name]
                
                thg_result = vectordotdev.assess_vrl_performance(vrl_code, test_data, pattern_name)
                results[pattern_name] = thg_result
                
            except Exception as e:
                results[pattern_name] = {"error": str(e), "thg_score": 0}
        
        return results


# Convenience exports for easy access
production_patterns = ProductionPatterns()

# Direct pattern access (instance methods)
def get_apache_combined():
    return production_patterns.get_apache_combined()

def get_nginx_access():
    return production_patterns.get_nginx_access()

def get_json_application():
    return production_patterns.get_json_application()

def get_kubernetes_pods():
    return production_patterns.get_kubernetes_pods()

def get_docker_container():
    return production_patterns.get_docker_container()
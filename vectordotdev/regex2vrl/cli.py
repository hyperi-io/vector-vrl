#!/usr/bin/env python3
"""
Command-line interface for regex2vrl
Convert regex and grok patterns to performant VRL code
"""

import argparse
import sys
import json
from pathlib import Path
from typing import Optional, List
from .core import RegexToVRL
from .grok_converter import GrokToVRL


class CLI:
    """Command-line interface for regex2vrl"""
    
    def __init__(self):
        self.regex_converter = RegexToVRL()
        self.grok_converter = GrokToVRL()
    
    def main(self):
        """Main CLI entry point"""
        parser = argparse.ArgumentParser(
            description='Convert regex and grok patterns to performant VRL code',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog='''
Examples:
  # Convert a regex pattern
  regex2vrl convert-regex "(?P<ip>\\d+\\.\\d+\\.\\d+\\.\\d+).*(?P<status>\\d{3})"
  
  # Convert a grok pattern
  regex2vrl convert-grok "%%{TIMESTAMP_ISO8601:timestamp} %%{LOGLEVEL:level} %%{GREEDYDATA:message}"
  
  # Analyze a pattern's performance
  regex2vrl analyze "(?P<timestamp>.*?) \\[(?P<level>\\w+)\\]"
  
  # Batch convert patterns from file
  regex2vrl batch patterns.txt --output vrl_parsers/
  
  # Show common patterns
  regex2vrl patterns --type apache
            '''
        )
        
        subparsers = parser.add_subparsers(dest='command', help='Commands')
        
        # Convert regex command
        regex_parser = subparsers.add_parser('convert-regex', help='Convert regex to VRL')
        regex_parser.add_argument('pattern', help='Regex pattern to convert')
        regex_parser.add_argument('--input-field', default='.message', 
                                 help='Input field to parse (default: .message)')
        regex_parser.add_argument('--output', '-o', help='Output file (default: stdout)')
        regex_parser.add_argument('--commented', action='store_true', 
                                 help='Include comments in output')
        
        # Convert grok command
        grok_parser = subparsers.add_parser('convert-grok', help='Convert grok to VRL')
        grok_parser.add_argument('pattern', help='Grok pattern to convert')
        grok_parser.add_argument('--input-field', default='.message', 
                                help='Input field to parse (default: .message)')
        grok_parser.add_argument('--output', '-o', help='Output file (default: stdout)')
        
        # Analyze command
        analyze_parser = subparsers.add_parser('analyze', help='Analyze pattern performance')
        analyze_parser.add_argument('pattern', help='Pattern to analyze')
        analyze_parser.add_argument('--type', choices=['regex', 'grok'], default='regex',
                                   help='Pattern type (default: regex)')
        
        # Batch command
        batch_parser = subparsers.add_parser('batch', help='Batch convert patterns')
        batch_parser.add_argument('input', help='Input file with patterns')
        batch_parser.add_argument('--output', '-o', required=True, 
                                 help='Output directory for VRL files')
        batch_parser.add_argument('--type', choices=['regex', 'grok', 'auto'], 
                                 default='auto', help='Pattern type (default: auto-detect)')
        
        # Patterns command
        patterns_parser = subparsers.add_parser('patterns', help='Show common patterns')
        patterns_parser.add_argument('--type', choices=['all', 'apache', 'nginx', 'syslog', 
                                                        'aws', 'docker', 'kubernetes'],
                                    default='all', help='Pattern category')
        
        # Test command
        test_parser = subparsers.add_parser('test', help='Test VRL output')
        test_parser.add_argument('pattern', help='Pattern to test')
        test_parser.add_argument('--sample', required=True, help='Sample log line to test')
        test_parser.add_argument('--type', choices=['regex', 'grok'], default='regex',
                                help='Pattern type (default: regex)')
        
        args = parser.parse_args()
        
        if not args.command:
            parser.print_help()
            return 0
        
        # Execute command
        if args.command == 'convert-regex':
            return self.convert_regex(args)
        elif args.command == 'convert-grok':
            return self.convert_grok(args)
        elif args.command == 'analyze':
            return self.analyze_pattern(args)
        elif args.command == 'batch':
            return self.batch_convert(args)
        elif args.command == 'patterns':
            return self.show_patterns(args)
        elif args.command == 'test':
            return self.test_pattern(args)
    
    def convert_regex(self, args):
        """Convert regex pattern to VRL"""
        try:
            output_format = 'commented' if args.commented else 'vrl'
            vrl_code = self.regex_converter.convert(
                args.pattern, 
                args.input_field,
                output_format
            )
            
            if args.output:
                Path(args.output).write_text(vrl_code)
                print(f"VRL code written to {args.output}")
            else:
                print(vrl_code)
            
            return 0
        except Exception as e:
            print(f"Error converting regex: {e}", file=sys.stderr)
            return 1
    
    def convert_grok(self, args):
        """Convert grok pattern to VRL"""
        try:
            vrl_code = self.grok_converter.convert(args.pattern, args.input_field)
            
            if args.output:
                Path(args.output).write_text(vrl_code)
                print(f"VRL code written to {args.output}")
            else:
                print(vrl_code)
            
            return 0
        except Exception as e:
            print(f"Error converting grok: {e}", file=sys.stderr)
            return 1
    
    def analyze_pattern(self, args):
        """Analyze pattern performance and structure"""
        try:
            if args.type == 'regex':
                analysis = self.regex_converter.analyze_pattern(args.pattern)
            else:
                # For grok, expand to regex first then analyze
                expanded = self.grok_converter._expand_grok_to_regex(args.pattern)
                analysis = self.regex_converter.analyze_pattern(expanded)
            
            print("Pattern Analysis")
            print("=" * 50)
            print(f"Pattern Type: {analysis.pattern_type.value}")
            print(f"Has Groups: {analysis.has_groups}")
            print(f"Has Named Groups: {analysis.has_named_groups}")
            print(f"Group Names: {', '.join(analysis.group_names) if analysis.group_names else 'None'}")
            print(f"Delimiters Found: {analysis.delimiters}")
            print(f"Field Count: {analysis.field_count}")
            print(f"Can Use Built-in Parser: {analysis.can_use_builtin}")
            print(f"Suggested Parser: {analysis.suggested_parser or 'None'}")
            print(f"Estimated THG Performance: {analysis.estimated_thg}")
            print()
            
            # Performance recommendation
            if analysis.estimated_thg >= 350:
                print("✅ Performance: EXCELLENT - This pattern will perform well")
            elif analysis.estimated_thg >= 200:
                print("⚠️  Performance: MODERATE - Consider optimization")
            else:
                print("❌ Performance: POOR - Needs optimization for production use")
            
            return 0
        except Exception as e:
            print(f"Error analyzing pattern: {e}", file=sys.stderr)
            return 1
    
    def batch_convert(self, args):
        """Batch convert patterns from file"""
        try:
            input_path = Path(args.input)
            output_dir = Path(args.output)
            
            if not input_path.exists():
                print(f"Input file not found: {args.input}", file=sys.stderr)
                return 1
            
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Read patterns
            patterns = []
            with open(input_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        patterns.append(line)
            
            print(f"Converting {len(patterns)} patterns...")
            
            for i, pattern in enumerate(patterns, 1):
                # Auto-detect type if needed
                if args.type == 'auto':
                    pattern_type = 'grok' if '%{' in pattern else 'regex'
                else:
                    pattern_type = args.type
                
                # Convert pattern
                if pattern_type == 'grok':
                    vrl_code = self.grok_converter.convert(pattern)
                else:
                    vrl_code = self.regex_converter.convert(pattern)
                
                # Write output
                output_file = output_dir / f"parser_{i:03d}.vrl"
                output_file.write_text(vrl_code)
                
                print(f"  [{i}/{len(patterns)}] Converted: {output_file.name}")
            
            print(f"\n✅ Successfully converted {len(patterns)} patterns")
            print(f"Output directory: {output_dir}")
            
            return 0
        except Exception as e:
            print(f"Error in batch conversion: {e}", file=sys.stderr)
            return 1
    
    def show_patterns(self, args):
        """Show common patterns and their VRL equivalents"""
        patterns = {
            'apache': {
                'description': 'Apache Combined Log Format',
                'grok': '%{HTTPD_COMBINEDLOG}',
                'vrl': 'parse_apache_log!(message, format: "combined")'
            },
            'nginx': {
                'description': 'Nginx Combined Log Format',
                'grok': '%{IPORHOST:clientip} %{USER:ident} %{USER:auth} \\[%{HTTPDATE:timestamp}\\] "%{WORD:verb} %{URIPATHPARAM:request} HTTP/%{NUMBER:httpversion}" %{NUMBER:response} %{NUMBER:bytes} "%{DATA:referrer}" "%{DATA:agent}"',
                'vrl': 'parse_nginx_log!(message, format: "combined")'
            },
            'syslog': {
                'description': 'Syslog Format',
                'grok': '%{SYSLOGBASE}',
                'vrl': 'parse_syslog!(message)'
            },
            'aws': {
                'description': 'AWS ALB Logs',
                'grok': 'Custom AWS pattern',
                'vrl': 'parse_aws_alb_log!(message)'
            },
            'docker': {
                'description': 'Docker Container Logs',
                'grok': '%{TIMESTAMP_ISO8601:timestamp} %{LOGLEVEL:level} %{GREEDYDATA:message}',
                'vrl': 'Custom VRL using split() and parse_timestamp()'
            },
            'kubernetes': {
                'description': 'Kubernetes Pod Logs',
                'grok': '%{TIMESTAMP_ISO8601:timestamp} %{WORD:stream} %{WORD:logtag} %{GREEDYDATA:message}',
                'vrl': 'Custom VRL for K8s logs'
            }
        }
        
        if args.type == 'all':
            items = patterns.items()
        else:
            items = [(args.type, patterns.get(args.type, {}))]
        
        for name, info in items:
            if info:
                print(f"\n{name.upper()} Pattern")
                print("=" * 50)
                print(f"Description: {info['description']}")
                print(f"Grok Pattern: {info['grok']}")
                print(f"VRL Equivalent: {info['vrl']}")
        
        return 0
    
    def test_pattern(self, args):
        """Test pattern against sample log"""
        try:
            print(f"Testing pattern against sample log...")
            print(f"Pattern: {args.pattern}")
            print(f"Sample: {args.sample}")
            print()
            
            # Convert pattern
            if args.type == 'grok':
                vrl_code = self.grok_converter.convert(args.pattern)
            else:
                vrl_code = self.regex_converter.convert(args.pattern)
            
            print("Generated VRL Code:")
            print("-" * 50)
            print(vrl_code)
            print("-" * 50)
            
            # Note: Actual testing would require VRL runtime
            print("\nNote: To test this VRL code, use Vector's test framework")
            print("or the VRL REPL with your sample data.")
            
            return 0
        except Exception as e:
            print(f"Error testing pattern: {e}", file=sys.stderr)
            return 1


def main():
    """Main entry point"""
    cli = CLI()
    return cli.main()


if __name__ == '__main__':
    sys.exit(main())
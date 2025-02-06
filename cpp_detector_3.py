import os
import re
from pathlib import Path
import json
from typing import Dict, List, Optional, Tuple

class DependencyAnalyzer:
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.dependencies: Dict[str, Optional[str]] = {}
        self.error_log_path = "cpp_parse_errors.txt"
        
        # Common package manager files
        self.package_files = [
            'conanfile.txt',
            'conanfile.py',
            'CMakeLists.txt',
            'vcpkg.json',
            'packages.config'
        ]
        
        # Regex patterns for version detection
        self.version_patterns = {
            'cmake': r'find_package\s*\(\s*(\w+)\s+(\d+[\.\d]*)',
            'include': r'#include\s*[<"](\w+)(?:/[\w\.]+)*[>"]',
            'conan': r'(\w+)/([\d\.]+)@',
            'vcpkg': r'"name":\s*"([^"]+)"[^}]+"version":\s*"([^"]+)"',
            'define': r'#define\s+(\w+_VERSION)\s+["]?([\d\.]+)["]?'
        }

    def log_error(self, error_message: str) -> None:
        """Write error message to the error log file."""
        with open(self.error_log_path, 'a', encoding='utf-8') as f:
            f.write(error_message + '\n')

    def analyze_file(self, file_path: Path) -> None:                                       
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            file_name = file_path.name.lower()
            
            # Check for package manager files
            if 'cmakelists.txt' in file_name:
                self._parse_cmake(content)
            elif 'conanfile' in file_name:
                self._parse_conan(content)
            elif 'vcpkg.json' in file_name:
                self._parse_vcpkg(content)
            # Check C++ source and header files
            elif file_path.suffix.lower() in ['.cpp', '.hpp', '.h', '.cc']:
                self._parse_cpp_file(content)
                
        except Exception as e:
            error_message = f"Error processing {file_path}: {str(e)}"
            print(error_message)  # Still print to console
            self.log_error(error_message)  # Also log to file

    def _parse_cmake(self, content: str) -> None:
        matches = re.finditer(self.version_patterns['cmake'], content)
        for match in matches:
            self.dependencies[match.group(1)] = match.group(2)

    def _parse_conan(self, content: str) -> None:
        matches = re.finditer(self.version_patterns['conan'], content)
        for match in matches:
            self.dependencies[match.group(1)] = match.group(2)

    def _parse_vcpkg(self, content: str) -> None:
        try:
            data = json.loads(content)
            if 'dependencies' in data:
                for dep in data['dependencies']:
                    if isinstance(dep, dict):
                        name = dep.get('name')
                        version = dep.get('version')
                        if name:
                            self.dependencies[name] = version
                    elif isinstance(dep, str):
                        self.dependencies[dep] = None
        except json.JSONDecodeError:
            # Fall back to regex for malformed JSON
            matches = re.finditer(self.version_patterns['vcpkg'], content)
            for match in matches:
                self.dependencies[match.group(1)] = match.group(2)

    def _parse_cpp_file(self, content: str) -> None:
        # Look for include statements
        includes = re.finditer(self.version_patterns['include'], content)
        for match in includes:
            lib_name = match.group(1)
            if lib_name not in ['string', 'vector', 'iostream']:  # Skip standard library
                self.dependencies.setdefault(lib_name, None)
        
        # Look for version defines
        defines = re.finditer(self.version_patterns['define'], content)
        for match in defines:
            lib_name = match.group(1).replace('_VERSION', '').lower()
            self.dependencies[lib_name] = match.group(2)

    def scan_project(self) -> Dict[str, Optional[str]]:
        """Scan the project directory for dependencies."""
        # Clear any existing error log file
        if os.path.exists(self.error_log_path):
            os.remove(self.error_log_path)
            
        for root, _, files in os.walk(self.project_path):
            for file in files:
                file_path = Path(root) / file
                self.analyze_file(file_path)
        return self.dependencies

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Analyze C++ project dependencies')
    parser.add_argument('project_path', help='Path to C++ project root directory')
    parser.add_argument('--output', '-o', help='Output JSON file path')
    args = parser.parse_args()

    analyzer = DependencyAnalyzer(args.project_path)
    dependencies = analyzer.scan_project()

    # Sort dependencies by name
    sorted_deps = dict(sorted(dependencies.items()))

    # Print results
    print("\nThird-party Components Found:")
    print("-" * 40)
    for name, version in sorted_deps.items():
        version_str = version if version else "Version not found"
        print(f"{name:<30} {version_str}")

    # Save to JSON if output file specified
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(sorted_deps, f, indent=2)
        print(f"\nResults saved to {args.output}")

    # Print error log status
    if os.path.exists(analyzer.error_log_path):
        print(f"\nSome errors occurred during processing. Check {analyzer.error_log_path} for details.")

if __name__ == "__main__":
    main()
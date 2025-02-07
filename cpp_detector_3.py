import os
import re
from pathlib import Path
import json
from typing import Dict, List, Optional, Tuple, Set

#TODO may want to deal with non utf-8 characters
#TODO improve version detection ... build hash library of top n C++ projects
#TODO guess platform? 
#TODO create an sbom output option

class DependencyAnalyzer:
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        # Structure to store both version and file locations
        self.dependencies: Dict[str, Dict[str, any]] = {}
        self.error_log_path = "cpp_parse_errors.txt"
        
        # package manager files. This is good enough (for now)
        self.package_files = [
            'conanfile.txt',
            'conanfile.py',
            'CMakeLists.txt',
            'vcpkg.json',
            'packages.config'
        ]
        
        # Regex patterns for version detection. am I missing anything?
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

    def _add_dependency(self, name: str, version: Optional[str], file_path: Path) -> None:
        """Add or update a dependency with its version and file location."""
        rel_path = str(file_path.relative_to(self.project_path))
        if name not in self.dependencies:
            self.dependencies[name] = {
                'version': version,
                'locations': {rel_path}
            }
        else:
            # Update version if we found one and didn't have one before
            if version and not self.dependencies[name]['version']:
                self.dependencies[name]['version'] = version
            self.dependencies[name]['locations'].add(rel_path)

    def analyze_file(self, file_path: Path) -> None:                                       
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            file_name = file_path.name.lower()
            
            # Check for package manager files
            if 'cmakelists.txt' in file_name:
                self._parse_cmake(content, file_path)
            elif 'conanfile' in file_name:
                self._parse_conan(content, file_path)
            elif 'vcpkg.json' in file_name:
                self._parse_vcpkg(content, file_path)
            # Check C++ source and header files
            elif file_path.suffix.lower() in ['.cpp', '.hpp', '.h', '.cc']:
                self._parse_cpp_file(content, file_path)
                
        except Exception as e:
            error_message = f"Error processing {file_path}: {str(e)}"
            print(error_message)
            self.log_error(error_message)

    def _parse_cmake(self, content: str, file_path: Path) -> None:
        matches = re.finditer(self.version_patterns['cmake'], content)
        for match in matches:
            self._add_dependency(match.group(1), match.group(2), file_path)

    def _parse_conan(self, content: str, file_path: Path) -> None:
        matches = re.finditer(self.version_patterns['conan'], content)
        for match in matches:
            self._add_dependency(match.group(1), match.group(2), file_path)

    def _parse_vcpkg(self, content: str, file_path: Path) -> None:
        try:
            data = json.loads(content)
            if 'dependencies' in data:
                for dep in data['dependencies']:
                    if isinstance(dep, dict):
                        name = dep.get('name')
                        version = dep.get('version')
                        if name:
                            self._add_dependency(name, version, file_path)
                    elif isinstance(dep, str):
                        self._add_dependency(dep, None, file_path)
        except json.JSONDecodeError:
            # Fall back to regex for malformed JSON
            matches = re.finditer(self.version_patterns['vcpkg'], content)
            for match in matches:
                self._add_dependency(match.group(1), match.group(2), file_path)

    def _parse_cpp_file(self, content: str, file_path: Path) -> None:
        # Look for include statements
        includes = re.finditer(self.version_patterns['include'], content)
        for match in includes:
            lib_name = match.group(1)
            if lib_name not in ['string', 'vector', 'iostream']:  # Skip standard library
                self._add_dependency(lib_name, None, file_path)
        
        # Look for version defines
        defines = re.finditer(self.version_patterns['define'], content)
        for match in defines:
            lib_name = match.group(1).replace('_VERSION', '').lower()
            self._add_dependency(lib_name, match.group(2), file_path)

    def scan_project(self) -> Dict[str, Dict[str, any]]:
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

    # output results to screen for now. 
    print("\nThird-party Components Found:")
    print("-" * 80)
    for name, info in sorted_deps.items():
        version_str = info['version'] if info['version'] else "Version not found"
        print(f"\n{name}:")
        print(f"  Version: {version_str}")
        print("  Found in:")
        for location in sorted(info['locations']):
            print(f"    - {location}")

    # Save to JSON if output file specified
    if args.output:
        # Convert sets to lists for JSON serialization
        json_deps = {
            name: {
                'version': info['version'],
                'locations': sorted(list(info['locations']))
            }
            for name, info in sorted_deps.items()
        }
        with open(args.output, 'w') as f:
            json.dump(json_deps, f, indent=2)
        print(f"\nResults saved to {args.output}")

    # print error log
    if os.path.exists(analyzer.error_log_path):
        print(f"\nSome errors occurred during processing. Check {analyzer.error_log_path} for details.")

if __name__ == "__main__":
    main()

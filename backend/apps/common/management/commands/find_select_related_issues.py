from django.core.management.base import BaseCommand
import os
import re


class Command(BaseCommand):
    help = 'Find potential select_related("tenant") issues in Python files'

    def add_arguments(self, parser):
        parser.add_argument(
            '--path', 
            default='.',
            help='Path to search (default: current directory)'
        )
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Attempt to automatically fix found issues'
        )

    def handle(self, *args, **options):
        path = options['path']
        fix_mode = options.get('fix', False)
        
        self.stdout.write(f"Searching for select_related('tenant') issues in {path}")
        
        # Files to exclude (migrations, settings, etc.)
        excludes = [
            'venv', 'migrations', 'node_modules', '.git',
            'settings.py', '__pycache__'
        ]
        
        issues_found = []
        
        # Walk through all Python files
        for root, dirs, files in os.walk(path):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if not any(ex in d for ex in excludes)]
            
            for file in files:
                if not file.endswith('.py'):
                    continue
                
                if any(ex in file for ex in excludes):
                    continue
                
                file_path = os.path.join(root, file)
                issues = self._check_file(file_path)
                
                if issues:
                    issues_found.extend(issues)
                    self.stdout.write(f"Found {len(issues)} issues in {file_path}")
                    
                    if fix_mode:
                        self._fix_file(file_path, issues)
        
        if not issues_found:
            self.stdout.write(self.style.SUCCESS("No issues found"))
            return
            
        self.stdout.write(self.style.WARNING(f"Found {len(issues_found)} issues in total"))
        
        # Group by file for display
        by_file = {}
        for issue in issues_found:
            file_path = issue['file']
            if file_path not in by_file:
                by_file[file_path] = []
            by_file[file_path].append(issue)
            
        # Display issues grouped by file
        for file_path, issues in by_file.items():
            self.stdout.write(f"\nFile: {file_path}")
            self.stdout.write("=" * 80)
            
            for issue in issues:
                self.stdout.write(f"Line {issue['line']}: {issue['content'].strip()}")
                if fix_mode and issue.get('fixed'):
                    self.stdout.write(f"   Fixed → {issue['fixed'].strip()}")
            
            self.stdout.write("-" * 80)
    
    def _check_file(self, file_path):
        issues = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        # Regular expressions to find potential issues
        patterns = [
            r'\.select_related\(\s*[\'"]tenant[\'"]\s*\)',
            r'\.select_related\([^\)]*[\'"]tenant[\'"]\s*[,\)]',
            r'tenant\s*=\s*.*\.tenant',
            r'request\.tenant',
            r'user\.tenant'
        ]
        
        for i, line in enumerate(lines):
            for pattern in patterns:
                if re.search(pattern, line):
                    issues.append({
                        'file': file_path,
                        'line': i + 1,
                        'content': line,
                        'pattern': pattern
                    })
        
        return issues
    
    def _fix_file(self, file_path, issues):
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        modified = False
        
        for issue in issues:
            line_idx = issue['line'] - 1
            line = lines[line_idx]
            pattern = issue['pattern']
            
            # Attempt to fix based on pattern type
            fixed_line = None
            
            if 'select_related' in pattern:
                # Remove tenant from select_related
                if '.select_related(' in line:
                    # Handle different forms of select_related
                    if '.select_related(\'tenant\')' in line:
                        fixed_line = line.replace('.select_related(\'tenant\')', '')
                    elif '' in line:
                        fixed_line = line.replace('', '')
                    elif 'tenant' in line:
                        # More complex case with multiple select_related arguments
                        # Use regex to remove just 'tenant' while preserving other fields
                        fixed_line = re.sub(
                            r'\.select_related\(([^)]*)[\'"]tenant[\'"]\s*,?\s*([^)]*)\)', 
                            r'.select_related(\1\2)', 
                            line
                        )
                        # Clean up any syntax issues (like double commas)
                        fixed_line = fixed_line.replace(',,', ',')
                        fixed_line = re.sub(r'\(\s*,', '(', fixed_line)
                        fixed_line = re.sub(r',\s*\)', ')', fixed_line)
                        fixed_line = re.sub(r'\(\s*\)', '', fixed_line)
            
            elif 'request.tenant' in pattern:
                # Replace request.tenant with request.tenant_schema
                fixed_line = re.sub(r'request\.tenant(?!_)', r'request.tenant_schema', line)
            
            elif 'user.tenant' in pattern:
                # Replace user.tenant with a safer alternative
                fixed_line = re.sub(r'user\.tenant(?!_)', r'user.tenant_schema', line)
                
            elif 'tenant = ' in pattern:
                # Depending on context, try to make a safe fix
                if 'tenant = ' in line and '.tenant' in line:
                    fixed_line = re.sub(
                        r'tenant\s*=\s*(.*?)\.tenant', 
                        r'tenant_schema = \1.tenant_schema', 
                        line
                    )
            
            if fixed_line and fixed_line != line:
                lines[line_idx] = fixed_line
                issue['fixed'] = fixed_line
                modified = True
        
        if modified:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            self.stdout.write(self.style.SUCCESS(f"Fixed issues in {file_path}"))

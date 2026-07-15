import os
import zipfile

def create_zip():
    zip_filename = "AWS_Optimization_Final.zip"
    
    if os.path.exists(zip_filename):
        os.remove(zip_filename)
        
    include_dirs = ['app', 'data', 'docs', 'tests', 'scripts']
    include_files = ['requirements.txt', 'README.md', 'test_run.py', 'setup_project.py']
    
    exclude_dirs = ['__pycache__', '.pytest_cache']
    
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk('.'):
            # Prune excluded dirs
            dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]
            
            # Check if root is in included dirs or is root
            path_parts = root.split(os.sep)
            if len(path_parts) > 1 and path_parts[1] in include_dirs:
                for file in files:
                    if file.endswith('.pyc') or file.endswith('.zip'):
                        continue
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, '.')
                    zipf.write(file_path, arcname)
            elif root == '.':
                for file in files:
                    if file in include_files:
                        zipf.write(file, file)

    print(f"Created {zip_filename}")

if __name__ == "__main__":
    create_zip()

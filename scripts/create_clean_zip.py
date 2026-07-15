import os
import zipfile

def create_zip(zip_path, folder_path):
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            # Exclude unwanted directories
            dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', 'venv', '.pytest_cache', '.gemini', '.idea', '.vscode', 'scripts']]
            
            for file in files:
                if file.endswith('.zip') or file.endswith('.pyc') or file == '.DS_Store' or file.startswith('debug'):
                    continue
                
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, folder_path)
                zipf.write(file_path, arcname)

create_zip("AWS_Optimization_Final.zip", ".")
print("Created AWS_Optimization_Final.zip successfully!")

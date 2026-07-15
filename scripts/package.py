import os
import zipfile

def create_zip(zip_name, source_dirs):
    print(f"Creating {zip_name}...")
    
    # Remove existing
    if os.path.exists(zip_name):
        os.remove(zip_name)
        
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk("."):
            # Exclusions
            if any(x in root for x in [".git", "__pycache__", ".pytest_cache", "venv", "outputs", ".streamlit"]):
                continue
                
            for file in files:
                if file.endswith(".pyc") or file.endswith(".log") or file.endswith(".lst") or file.endswith(".lxi"):
                    continue
                if file in [zip_name, "debug.lp", "inspect.txt"]:
                    continue
                if root == ".\scripts" and (file.startswith("debug_") or file.startswith("fix_") or file.startswith("patch_")):
                    continue
                    
                filepath = os.path.join(root, file)
                
                # Check 0 byte files
                if os.path.getsize(filepath) == 0:
                    continue
                    
                arcname = os.path.relpath(filepath, ".")
                # Force forward slashes for cross-platform compatibility
                arcname = arcname.replace(os.sep, '/')
                
                # We only zip if it's in the allowed source dirs or root allowed files
                parts = arcname.split('/')
                if parts[0] in source_dirs or (len(parts) == 1 and file in ["README.md", "requirements.txt", "pytest.ini", "requirements-dev.txt"]):
                    zipf.write(filepath, arcname)
                    
    print("Done!")

if __name__ == "__main__":
    create_zip("AWS_Optimization_Final.zip", ["app", "data", "docs", "gams", "scripts", "tests"])

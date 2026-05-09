import json
from pathlib import Path

def get_all_py_files_recursively(root_dir, output_json):
    # Convert string path to a Path object
    base_path = Path(root_dir)
    code_library = []

    # .glob('**/*.py') searches all subdirectories recursively
    for file_path in base_path.glob('**/*.py'):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code_library.append({
                    "relative_path": str(file_path.relative_to(base_path)),
                    "filename": file_path.name,
                    "content": f.read()
                })
        except Exception as e:
            print(f"Could not read {file_path}: {e}")

    # Write the compiled list to a JSON file
    with open(output_json, 'w', encoding='utf-8') as jf:
        json.dump(code_library, jf, indent=4)
    
    print(f"Successfully processed {len(code_library)} files into {output_json}")

# Usage
# Change '.' to your project folder path
get_all_py_files_recursively('app/', 'full_project_code.json')
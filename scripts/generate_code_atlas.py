import os
import ast
import json
import re

def parse_python_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        tree = ast.parse(content)
    except Exception as e:
        return None

    data = {
        'functions': [],
        'classes': [],
        'endpoints': []
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # Check for endpoint decorators
            is_endpoint = False
            path = ""
            method = ""
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                    if dec.func.attr in ['get', 'post', 'put', 'delete', 'patch']:
                        is_endpoint = True
                        method = dec.func.attr.upper()
                        if dec.args and isinstance(dec.args[0], ast.Constant):
                            path = dec.args[0].value

            return_type = "Untyped"
            if node.returns:
                if isinstance(node.returns, ast.Name):
                    return_type = node.returns.id
                elif hasattr(node.returns, 'id'):
                    return_type = node.returns.id
                else:
                    return_type = "Complex Type"
            
            calls = []
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    if isinstance(child.func, ast.Name):
                        calls.append(child.func.id)
                    elif isinstance(child.func, ast.Attribute):
                        calls.append(child.func.attr)
            calls = list(set(calls))

            func_info = {
                'name': node.name,
                'docstring': ast.get_docstring(node) or "",
                'args': [arg.arg for arg in node.args.args],
                'returns': return_type,
                'calls': calls,
                'line_number': node.lineno
            }

            if is_endpoint:
                data['endpoints'].append({
                    **func_info,
                    'method': method,
                    'path': path
                })
            else:
                data['functions'].append(func_info)

        elif isinstance(node, ast.ClassDef):
            fields = []
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    fields.append(item.target.id)
            
            data['classes'].append({
                'name': node.name,
                'docstring': ast.get_docstring(node) or "",
                'fields': fields,
                'line_number': node.lineno
            })

    return data

def build_atlas(root_dir):
    atlas = {
        'files': {},
        'all_endpoints': [],
        'all_models': [],
        'all_modules': []
    }

    for dirpath, _, filenames in os.walk(root_dir):
        if 'venv' in dirpath or '__pycache__' in dirpath:
            continue
            
        for filename in filenames:
            if filename.endswith('.py'):
                filepath = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(filepath, start=os.path.dirname(root_dir))
                
                parsed_data = parse_python_file(filepath)
                if parsed_data:
                    atlas['files'][rel_path] = parsed_data
                    atlas['all_modules'].append({'name': rel_path, 'file': rel_path})
                    for ep in parsed_data['endpoints']:
                        atlas['all_endpoints'].append({**ep, 'file': rel_path})
                    for cls in parsed_data['classes']:
                        atlas['all_models'].append({**cls, 'file': rel_path})

    return atlas

if __name__ == "__main__":
    backend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend')
    atlas_data = build_atlas(backend_dir)
    
    out_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'code_atlas.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(atlas_data, f, indent=2)
    print(f"Generated Code Atlas at {out_path}")

import shutil
import folder_paths
import os, sys
import subprocess


sys.path.append('../..')

from torchvision.datasets.utils import download_url

# ensure .js
print("### Loading: ComfyUI-Manager (V0.3)")

comfy_path = os.path.dirname(folder_paths.__file__)
custom_nodes_path = os.path.join(comfy_path, 'custom_nodes')
js_path = os.path.join(comfy_path, "web", "extensions")

comfyui_manager_path = os.path.dirname(__file__)
local_db_model = os.path.join(comfyui_manager_path, "model-list.json")
local_db_alter = os.path.join(comfyui_manager_path, "alter-list.json")
local_db_custom_node_list = os.path.join(comfyui_manager_path, "custom-node-list.json")


def git_repo_has_updates(path):
    # Check if the path is a git repository
    if not os.path.exists(os.path.join(path, '.git')):
        raise ValueError('Not a git repository')

    # Fetch the latest commits from the remote repository
    subprocess.run(['git', 'fetch'], check=True, cwd=path)

    # Get the current commit hash and the commit hash of the remote branch
    commit_hash = subprocess.check_output(['git', 'rev-parse', 'HEAD'], encoding='utf-8', cwd=path).strip()
    remote_commit_hash = subprocess.check_output(['git', 'rev-parse', '@{u}'], encoding='utf-8', cwd=path).strip()

    # Compare the commit hashes to determine if the local repository is behind the remote repository
    if commit_hash != remote_commit_hash:
        return True

    return False


def git_pull(path):
    print(f"path: {path}")
    if not os.path.exists(os.path.join(path, '.git')):
        raise ValueError('Not a git repository')

    subprocess.run(['git', 'pull'], check=True, cwd=path)


async def get_data(uri):
    print(f"FECTH DATA from: {uri}")
    if uri.startswith("http"):
        async with aiohttp.ClientSession() as session:
            async with session.get(uri) as resp:
                json_text = await resp.text()
    else:
        with open(uri, "r") as f:
            json_text = f.read()

    json_obj = json.loads(json_text)
    return json_obj


def setup_js():
    # remove garbage
    old_js_path = os.path.join(comfy_path, "web", "extensions", "core", "comfyui-manager.js")
    if os.path.exists(old_js_path):
        os.remove(old_js_path)

    # setup js
    js_dest_path = os.path.join(js_path, "comfyui-manager")
    if not os.path.exists(js_dest_path):
        os.makedirs(js_dest_path)
    js_src_path = os.path.join(comfyui_manager_path, "js", "comfyui-manager.js")
    shutil.copy(js_src_path, js_dest_path)

setup_js()


# Expand Server api

import server
from aiohttp import web
import aiohttp
import json
import zipfile
import urllib.request


def get_model_path(data):
    if data['save_path'] != 'default':
        base_model = os.path.join(folder_paths.models_dir, data['save_path'])
    else:
        model_type = data['type']
        if model_type == "checkpoints":
            base_model = folder_paths.folder_names_and_paths["checkpoints"][0][0]
        elif model_type == "unclip":
            base_model = folder_paths.folder_names_and_paths["checkpoints"][0][0]
        elif model_type == "VAE":
            base_model = folder_paths.folder_names_and_paths["vae"][0][0]
        elif model_type == "lora":
            base_model = folder_paths.folder_names_and_paths["loras"][0][0]
        elif model_type == "T2I-Adapter":
            base_model = folder_paths.folder_names_and_paths["controlnet"][0][0]
        elif model_type == "T2I-Style":
            base_model = folder_paths.folder_names_and_paths["controlnet"][0][0]
        elif model_type == "controlnet":
            base_model = folder_paths.folder_names_and_paths["controlnet"][0][0]
        elif model_type == "clip_vision":
            base_model = folder_paths.folder_names_and_paths["clip_vision"][0][0]
        elif model_type == "gligen":
            base_model = folder_paths.folder_names_and_paths["gligen"][0][0]
        elif model_type == "upscale":
            base_model = folder_paths.folder_names_and_paths["upscale_models"][0][0]
        elif model_type == "embeddings":
            base_model = folder_paths.folder_names_and_paths["embeddings"][0][0]
        else:
            base_model = None

    return os.path.join(base_model, data['filename'])


def check_a_custom_node_installed(item):
    item['installed'] = 'None'

    if item['install_type'] == 'git-clone' and len(item['files']) == 1:
        dir_name = os.path.splitext(os.path.basename(item['files'][0]))[0].replace(".git", "")
        dir_path = os.path.join(custom_nodes_path, dir_name)
        if os.path.exists(dir_path):
            try:
                if git_repo_has_updates(dir_path):
                    item['installed'] = 'Update'
                else:
                    item['installed'] = 'True'
            except:
                item['installed'] = 'True'

        elif os.path.exists(dir_path+".disabled"):
            item['installed'] = 'Disabled'

        else:
            item['installed'] = 'False'

    elif item['install_type'] == 'copy' and len(item['files']) == 1:
        dir_name = os.path.basename(item['files'][0])
        base_path = custom_nodes_path if item['files'][0].endswith('.py') else js_path
        file_path = os.path.join(base_path, dir_name)
        if os.path.exists(file_path):
            item['installed'] = 'True'
        elif os.path.exists(file_path + ".disabled"):
            item['installed'] = 'Disabled'
        else:
            item['installed'] = 'False'


def check_custom_nodes_installed(json_obj):
    for item in json_obj['custom_nodes']:
        check_a_custom_node_installed(item)


@server.PromptServer.instance.routes.get("/customnode/getlist")
async def fetch_customnode_list(request):
    if request.rel_url.query["mode"] == "local":
        uri = local_db_custom_node_list
    else:
        uri = 'https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/custom-node-list.json'

    json_obj = await get_data(uri)
    check_custom_nodes_installed(json_obj)

    return web.json_response(json_obj, content_type='application/json')


@server.PromptServer.instance.routes.get("/alternatives/getlist")
async def fetch_alternatives_list(request):
    if request.rel_url.query["mode"] == "local":
        uri1 = local_db_alter
        uri2 = local_db_custom_node_list
    else:
        uri1 = 'https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/alter-list.json'
        uri2 = 'https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/custom-node-list.json'

    alter_json = await get_data(uri1)
    custom_node_json = await get_data(uri2)

    fileurl_to_custom_node = {}
    for item in custom_node_json['custom_nodes']:
        for fileurl in item['files']:
            fileurl_to_custom_node[fileurl] = item

    for item in alter_json['items']:
        fileurl = item['id']
        if fileurl in fileurl_to_custom_node:
            custom_node = fileurl_to_custom_node[fileurl]
            check_a_custom_node_installed(custom_node)
            item['custom_node'] = custom_node

    return web.json_response(alter_json, content_type='application/json')


def check_model_installed(json_obj):
    for item in json_obj['models']:
        item['installed'] = 'None'

        model_path = get_model_path(item)

        if model_path is not None:
            if os.path.exists(model_path):
                item['installed'] = 'True'
            else:
                item['installed'] = 'False'


@server.PromptServer.instance.routes.get("/externalmodel/getlist")
async def fetch_externalmodel_list(request):
    if request.rel_url.query["mode"] == "local":
        uri = local_db_model
    else:
        uri = 'https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/model-list.json'


    json_obj = await get_data(uri)
    check_model_installed(json_obj)

    return web.json_response(json_obj, content_type='application/json')


def unzip_install(files):
    temp_filename = 'manager-temp.zip'
    for url in files:
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
            
            req = urllib.request.Request(url, headers=headers)
            response = urllib.request.urlopen(req)
            data = response.read()

            with open(temp_filename, 'wb') as f:
                f.write(data)

            with zipfile.ZipFile(temp_filename, 'r') as zip_ref:
                zip_ref.extractall(custom_nodes_path)

            os.remove(temp_filename)
        except Exception as e:
            print(f"Install(unzip) error: {url} / {e}")
            return False
    
    print("Installation was successful.")
    return True


def download_url_with_agent(url, save_path):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}

        req = urllib.request.Request(url, headers=headers)
        response = urllib.request.urlopen(req)
        data = response.read()

        with open(save_path, 'wb') as f:
            f.write(data)

    except Exception as e:
        print(f"Download error: {url} / {e}")
        return False

    print("Installation was successful.")
    return True


def copy_install(files, js_path_name=None):
    for url in files:
        try:
            if url.endswith(".py"):
                download_url(url, custom_nodes_path)
            else:
                path = os.path.join(js_path, js_path_name) if js_path_name is not None else js_path
                if not os.path.exists(path):
                    os.makedirs(path)
                download_url(url, path)

        except Exception as e:
            print(f"Install(copy) error: {url} / {e}")
            return False
    
    print("Installation was successful.")
    return True


def copy_uninstall(files, js_path_name=None):
    for url in files:
        dir_name = os.path.basename(url)
        base_path = custom_nodes_path if url.endswith('.py') else os.path.join(js_path, js_path_name)
        file_path = os.path.join(base_path, dir_name)

        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            elif os.path.exists(file_path+".disabled"):
                os.remove(file_path+".disabled")
        except Exception as e:
            print(f"Uninstall(copy) error: {url} / {e}")
            return False
        
    print("Uninstallation was successful.")
    return True


def copy_set_active(files, is_disable, js_path_name=None):
    if is_disable:
        action_name = "Disable"
    else:
        action_name = "Enable"

    for url in files:
        dir_name = os.path.basename(url)
        base_path = custom_nodes_path if url.endswith('.py') else os.path.join(js_path, js_path_name)
        file_path = os.path.join(base_path, dir_name)

        try:
            if is_disable:
                current_name = file_path
                new_name = file_path + ".disabled"
            else:
                current_name = file_path + ".disabled"
                new_name = file_path

            os.rename(current_name, new_name)

        except Exception as e:
            print(f"{action_name}(copy) error: {url} / {e}")

            return False

    print(f"{action_name} was successful.")
    return True


def execute_install_script(url, repo_path):
    install_script_path = os.path.join(repo_path, "install.py")
    requirements_path = os.path.join(repo_path, "requirements.txt")

    if os.path.exists(requirements_path):
        print(f"Install: pip packages")
        install_cmd = [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
        code = subprocess.run(install_cmd, cwd=repo_path)

        if code.returncode != 0:
            print(f"install script failed: {url}")
            return False

    if os.path.exists(install_script_path):
        print(f"Install: install script")
        install_cmd = [sys.executable, "install.py"]
        code = subprocess.run(install_cmd, cwd=repo_path)

        if code.returncode != 0:
            print(f"install script failed: {url}")
            return False

    return True

def gitclone_install(files):
    print(f"install: {files}")
    for url in files:
        try:
            print(f"Download: git clone '{url}'")
            clone_cmd = ["git", "clone", url]
            code = subprocess.run(clone_cmd, cwd=custom_nodes_path)
            
            if code.returncode != 0:
                print(f"git-clone failed: {url}")
                return False
                
            repo_name = os.path.splitext(os.path.basename(url))[0]
            repo_path = os.path.join(custom_nodes_path, repo_name)

            if not execute_install_script(url, repo_path):
                return False
            
        except Exception as e:
            print(f"Install(git-clone) error: {url} / {e}")
            return False
        
    print("Installation was successful.")
    return True


def gitclone_uninstall(files):
    import shutil
    import os

    print(f"uninstall: {files}")
    for url in files:
        try:
            dir_name = os.path.splitext(os.path.basename(url))[0].replace(".git", "")
            dir_path = os.path.join(custom_nodes_path, dir_name)

            # safey check
            if dir_path == '/' or dir_path[1:] == ":/" or dir_path == '':
                print(f"Uninstall(git-clone) error: invalid path '{dir_path}' for '{url}'")
                return False

            if os.path.exists(dir_path):
                shutil.rmtree(dir_path)
            elif os.path.exists(dir_path+".disabled"):
                shutil.rmtree(dir_path+".disabled")
        except Exception as e:
            print(f"Uninstall(git-clone) error: {url} / {e}")
            return False
        
    print("Uninstallation was successful.")
    return True


def gitclone_set_active(files, is_disable):
    import os

    if is_disable:
        action_name = "Disable"
    else:
        action_name = "Enable"

    print(f"{action_name}: {files}")
    for url in files:
        try:
            dir_name = os.path.splitext(os.path.basename(url))[0].replace(".git", "")
            dir_path = os.path.join(custom_nodes_path, dir_name)

            # safey check
            if dir_path == '/' or dir_path[1:] == ":/" or dir_path == '':
                print(f"{action_name}(git-clone) error: invalid path '{dir_path}' for '{url}'")
                return False

            if is_disable:
                current_path = dir_path
                new_path = dir_path + ".disabled"
            else:
                current_path = dir_path + ".disabled"
                new_path = dir_path

            os.rename(current_path, new_path)

        except Exception as e:
            print(f"{action_name}(git-clone) error: {url} / {e}")
            return False

    print(f"{action_name} was successful.")
    return True


def gitclone_update(files):
    import os

    print(f"update: {files}")
    for url in files:
        try:
            repo_name = os.path.splitext(os.path.basename(url))[0].replace(".git", "")
            repo_path = os.path.join(custom_nodes_path, repo_name)
            git_pull(repo_path)

            if not execute_install_script(url, repo_path):
                return False
            
        except Exception as e:
            print(f"Update(git-clone) error: {url} / {e}")
            return False
        
    print("Update was successful.")
    return True


@server.PromptServer.instance.routes.post("/customnode/install")
async def install_custom_node(request):
    json_data = await request.json()
    
    install_type = json_data['install_type']
    
    print(f"Install custom node '{json_data['title']}'")

    res = False

    if install_type == "unzip":
        res = unzip_install(json_data['files'])

    if install_type == "copy":
        js_path_name = json_data['js_path'] if 'js_path' in json_data else None
        res = copy_install(json_data['files'], js_path_name)
        
    elif install_type == "git-clone":
        res = gitclone_install(json_data['files'])
    
    if res:
        return web.json_response({}, content_type='application/json')
    
    return web.Response(status=400)


@server.PromptServer.instance.routes.post("/customnode/uninstall")
async def install_custom_node(request):
    json_data = await request.json()
    
    install_type = json_data['install_type']
    
    print(f"Uninstall custom node '{json_data['title']}'")

    res = False

    if install_type == "copy":
        js_path_name = json_data['js_path'] if 'js_path' in json_data else None
        res = copy_uninstall(json_data['files'], js_path_name)
        
    elif install_type == "git-clone":
        res = gitclone_uninstall(json_data['files'])
    
    if res:
        return web.json_response({}, content_type='application/json')
    
    return web.Response(status=400)


@server.PromptServer.instance.routes.post("/customnode/update")
async def install_custom_node(request):
    json_data = await request.json()
    
    install_type = json_data['install_type']
    
    print(f"Update custom node '{json_data['title']}'")

    res = False

    if install_type == "git-clone":
        res = gitclone_update(json_data['files'])
    
    if res:
        return web.json_response({}, content_type='application/json')
    
    return web.Response(status=400)


@server.PromptServer.instance.routes.post("/customnode/toggle_active")
async def install_custom_node(request):
    json_data = await request.json()

    install_type = json_data['install_type']
    is_disabled = json_data['installed'] == "Disabled"

    print(f"Update custom node '{json_data['title']}'")

    res = False

    if install_type == "git-clone":
        res = gitclone_set_active(json_data['files'], not is_disabled)
    elif install_type == "copy":
        res = copy_set_active(json_data['files'], not is_disabled)

    if res:
        return web.json_response({}, content_type='application/json')

    return web.Response(status=400)


@server.PromptServer.instance.routes.post("/model/install")
async def install_model(request):
    json_data = await request.json()

    model_path = get_model_path(json_data)

    res = False

    if model_path is not None:
        print(f"Install model '{json_data['name']}' into '{model_path}'")
        res = download_url_with_agent(json_data['url'], model_path)
    else:
        print(f"Model installation error: invalid model type - {json_data['type']}")

    if res:
        return web.json_response({}, content_type='application/json')

    return web.Response(status=400)


NODE_CLASS_MAPPINGS = {}
__all__ = ['NODE_CLASS_MAPPINGS']
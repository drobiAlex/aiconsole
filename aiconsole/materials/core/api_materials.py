"""
## Location

Materials are stored in the `./manuals` directory. Each material is a .md or a .py file.

## Writing Materials

When you need to write a material based on a conversation so far, extract key information from this conversation in very consise form. The goal is for you to read those instructions later, and be able to do this faster next time.
"""

import os
from aiconsole.materials.materials import materials
from aiconsole.settings import MATERIALS_DIRECTORY


def list_materials():
    return [{"id": material.id, "usage": material.usage} for material in materials.all_materials()]

def create_material(id: str, usage: str, header: str, content: str):
    # use lower case letters and underscores for spaces
    id = id.lower().replace(" ", "_").replace("-", "_")

    file_path = os.path.join(MATERIALS_DIRECTORY, f'{id}.md')

    if os.path.exists(file_path):
        raise Exception(f"Material with id {id} already exists")
    
    with open(file_path, 'w') as f:
        f.write(f"""
<!---
{usage}
-->

# {header}

{content}

""".strip())
        
    print (f"Material with id {id} created")
        
def read_material(id: str):
    path = os.path.join(MATERIALS_DIRECTORY, f'{id}.md')

    if not os.path.exists(path):
        raise Exception(f"Material with id {id} does not exist")
    
    with open(path, 'r') as f:
        return f.read()

material = {
    "usage": "Contains an API for manipulating AIConsole materials (saving, editing etc). If you just need a material the director should provide it to you without needing for this. Do not use if not tasked to directly manipulate materials.",
}
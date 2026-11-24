from pathlib import Path
import subprocess

def render_native(project: Path, output: Path, *, executable='apex'):
    subprocess.run([executable,'validate',str(project)],check=True)
    subprocess.run([executable,'render',str(project),'-o',str(output)],check=True)
    if not output.is_file() or output.stat().st_size==0: raise RuntimeError('missing render')
    return output

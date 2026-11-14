"""Run on each target OS with PyInstaller installed; produces native desktop artifacts."""
from pathlib import Path
import shutil
import os
import subprocess
import sys
import tempfile

project = Path(__file__).resolve().parents[1]
out = project / 'public/downloads'
name = 'MidsDenCompanion'
# Render the website's vector mark for native executable / app-bundle icons.
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage,QPainter
from PySide6.QtSvg import QSvgRenderer
out.mkdir(parents=True,exist_ok=True)
renderer=QSvgRenderer(str(project/'companion/ui/app-icon.svg'))
def render_icon(size,path):
    image=QImage(size,size,QImage.Format.Format_ARGB32);image.fill(0)
    painter=QPainter(image);renderer.render(painter,QRectF(0,0,size,size));painter.end()
    if not image.save(str(path)):raise RuntimeError('Could not write application icon: '+str(path))
icon_args=[]
if sys.platform=='win32':
    render_icon(256,out/'app-icon.ico');icon_args=['--icon',str(out/'app-icon.ico')]
elif sys.platform=='darwin':
    with tempfile.TemporaryDirectory() as directory:
        iconset=Path(directory)/'AppIcon.iconset';iconset.mkdir()
        for size in (16,32,128,256,512):
            render_icon(size,iconset/f'icon_{size}x{size}.png')
            render_icon(size*2,iconset/f'icon_{size}x{size}@2x.png')
        subprocess.run(['iconutil','-c','icns',str(iconset),'-o',str(out/'app-icon.icns')],check=True)
    icon_args=['--icon',str(out/'app-icon.icns')]
subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--windowed',
    '--exclude-module','tkinter','--exclude-module','PySide6.QtWidgets',
    '--add-data',str(project/'companion/measurement-units.json')+os.pathsep+'.',
    '--add-data',str(project/'companion/ui')+os.pathsep+'ui',
    '--hidden-import','PySide6.QtSvg',
    *icon_args,'--name',name,'--distpath',str(out),str(project/'companion/desktop.py')],check=True)
if sys.platform == 'win32':
    compiler = shutil.which('ISCC')
    if not compiler:
        raise SystemExit('Desktop EXE built. Install Inno Setup on the build machine to create the setup EXE.')
    subprocess.run([compiler, str(project / 'companion/windows-installer.iss')], check=True)
elif sys.platform == 'darwin':
    with tempfile.TemporaryDirectory() as folder:
        stage = Path(folder)
        shutil.copytree(out / (name + '.app'), stage / (name + '.app'), symlinks=True)
        (stage / 'Applications').symlink_to('/Applications')
        subprocess.run(['hdiutil', 'create', '-volname', "Mid's Den Companion", '-srcfolder', str(stage), '-ov', str(out / 'mids-den-companion-macos.dmg')], check=True)

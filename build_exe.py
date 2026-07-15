import PyInstaller.__main__

PyInstaller.__main__.run([
    'run_app.py',           
    '--onefile',             
    '--name', 'loby_backend',
    '--distpath', 'dist',    
    '--console'              
])

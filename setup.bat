rem batch script to run setup.py with approprate options
set version=savutil-0.1

rem create initial distribution

rmdir .\%version% /s/q
rmdir .\build /s/q
c:\python27\python setup.py py2exe --dist-dir=%version% --packages encodings
rmdir .\build /s/q
rmdir .\output /s/q
mkdir .\output
copy readme.html .\output\*
move /y .\savutil-0.1\sav2json.exe .\output\sav2json.exe
move /y .\savutil-0.1\json2sss.exe .\output\json2sss.exe
rmdir .\savutil-0.1 /s/q

rem batch script to run setup.py with approprate options

rem create distribution in .\output folder using .\temp folder
rem for working storage

rmdir .\temp /s/q
rmdir .\build /s/q
c:\python27\python setup.py py2exe --dist-dir=temp --packages encodings
rmdir .\build /s/q
rmdir .\output /s/q
mkdir .\output
copy readme.html .\output\*
if exist spss xcopy /s /i .\spss .\output\spss
move /y .\temp\sav2json.exe .\output\sav2json.exe
move /y .\temp\json2sss.exe .\output\json2sss.exe
rmdir .\temp /s/q

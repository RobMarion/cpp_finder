# cpp_finder
Author: R. Marion

## To use:
python cpp_finder_3.py {directory name} [-o {output file name}]  
The output is in json, so you might want to give the file a .json extension  

## Notes:
This is in early draft state.   
This does a decent job of parsing a directory for 3rd-party C++ in a code base. It looks for several package types, including CMake and Conan. It will also look for #include within files. This does not do transitive dependencies.  

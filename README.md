Numerical atomic orbital module for PySCF
=========================================

2021-02-27

* Version 0.1

Warnings
--------

PySCF NAO is no longer maintained, please use its successor [PyNAO](https://gitlab.com/mbarbry/pynao) instead.


Install
-------
* Install to python site-package folder
```
pip install https://github.com/pyscf/nao
```

* Install in a custom folder for development
```
git clone https://github.com/pyscf/nao /home/abc/local/path

# Set pyscf extended module path
echo 'export PYSCF_EXT_PATH=/home/abc/local/path:$PYSCF_EXT_PATH' >> ~/.bashrc
```

You can find more details of extended modules in the document
[extension modules](http://pyscf.org/pyscf/install.html#extension-modules)

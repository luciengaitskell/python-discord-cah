from setuptools import setup, find_packages

VERSION = 1.0
CAH_VERSION = 1.4

setup(name='python-discord-cah',
      version=VERSION ,
      description='A Cards Against Humanity discord bot',
      author='Lucien Gaitskell',
      url='https://github.com/luciengaitskell',
      install_requires=['python-cah==' + str(CAH_VERSION), 'discord.py'],
      dependency_links=[('http://github.com/luciengaitskell/python-cah/tarball/master#egg=python-cah-'
                         + str(CAH_VERSION))],
      packages=find_packages()
      )

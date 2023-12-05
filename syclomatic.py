import os, sys
import subprocess 

import time
import fire
import shutil
from c2s import Cuda2Sycl


class Syclomatic(Cuda2Sycl):
	def __init__(self, input_dir, include="", exclude="", min_index=0, max_index=-1, verbose=False):
		super().__init__(input_dir, include=include, exclude=exclude, 
						 min_index=min_index, max_index=max_index, verbose=verbose)
	
	def run(self):
		self.convert()
		self.compile(target="syclomatic")
		self.execute(target="syclomatic")
		self.plot()

def main(
		in_root: str,
		include: str="",
		exclude: str="",
		min_index: int=0,
		max_index: int=-1,
		verbose: bool=False,
		**kwargs
		):
	
	syclomatic = Syclomatic(in_root, include=include, exclude=exclude, 
						    min_index=min_index, max_index=max_index, verbose=verbose)
	syclomatic.run()
	

if __name__ == "__main__":
	fire.Fire(main)

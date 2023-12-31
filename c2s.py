import os, sys
import subprocess 
import time
from time import perf_counter
import shutil
import numpy as np
import pandas as pd
from tqdm import tqdm
import matplotlib.pyplot as plt
import concurrent.futures as cf
from threading import Lock, Timer
from cprint import *
import glob
import logging


class Cuda2Sycl():
	def __init__(self, input_dir, include="", exclude="", min_index=None, max_index=None, 
				       name="c2s", visualize=False, verbose=False):
		self.lock = Lock()
		self.input_dir = input_dir
		self.name = name
		self.visualize = visualize
		self.verbose = verbose

		to_include = include.split()
		to_exclude = exclude.split()

		self.df = pd.DataFrame(columns=['cuda', 'sycl', 'syclomatic', 'converted', 'compiled', 'executed', 'time']) 

		cuda_dirs = sorted(glob.glob(os.path.join(input_dir,"*-cuda"), recursive=False))
		sycl_dirs = glob.glob(os.path.join(input_dir,"*-sycl"), recursive=False)

		min_index = self.get_index(min_index, cuda_dirs, 0)
		max_index = self.get_index(max_index, cuda_dirs, len(cuda_dirs))

		for idx in range(min_index, max_index+1):
			cuda_dir = cuda_dirs[idx]
			base_name = os.path.basename(cuda_dir).split('-')[0]
			if len(to_include) > 0 and base_name not in to_include:
				continue
			if base_name in  to_exclude:
				continue
			base_dir = '-'.join(cuda_dir.split("-")[:-1])
			sycl_dir =  base_dir + '-sycl'
			syclomatic_dir =  base_dir + '-syclomatic'
			if sycl_dir in sycl_dirs:
				row = { 'cuda': cuda_dir, 'sycl': sycl_dir, 'syclomatic': syclomatic_dir, 
						'converted': False, 'compiled': False, 'executed': False, 'time': -1 }
				self.df = self.df._append(row, ignore_index = True)

		self.commands = {
			'convert' : 'c2s --in-root={}  --out-root={} --process-all',
			'compile' : 'make -C  {}',
			'run' : 'make -C {} {}'
		}
	
	def convert(self):
		def pre_process(index):
			in_root = self.df.loc[index, "cuda"]
			out_root = self.df.loc[index, "syclomatic"]
			shutil.rmtree(out_root, ignore_errors=True)
			return self.commands['convert'].format(in_root, out_root)

		def post_process(index):
			sycl_makefile = self.get_makefile(self.df.loc[index, "sycl"])
			syclomatic_makefile =  self.get_makefile(self.df.loc[index, "syclomatic"])

			if sycl_makefile is None or syclomatic_makefile is None:
				return

			with open(syclomatic_makefile, "w") as fw:
				with open(sycl_makefile) as fr:
					for line in fr:
						line = line.replace("clang++", "icpx")
						if line.startswith("#include"):
							line = line.replace(".dp.", ".")
						elif line.startswith("VERIFY"):
							line = line.replace("no", "yes")
						elif line.startswith("GCC_TOOLCHAIN"):
							continue
						fw.write(line)

			cd_cmd = f'cd {self.df.loc[index, "syclomatic"]} && '
			rename_cmd = cd_cmd + " find . -depth -execdir rename 's/.dp././g' '{}' \;"
			os.system(rename_cmd)

			modify_include_cmd = cd_cmd + "find . -type f -regex '.*\.\(hpp\|cpp\|c\|h\)' -exec sed -i -e '/^#include/s/\.dp\./\./g' {} +"
			os.system(modify_include_cmd)


		self.process(pre_process, post_process, name="Converting", update='converted')

	def compile(self, target):
		
		def build(index):
			syclomatic_makefile = self.get_makefile(self.df.loc[index, target])
			if syclomatic_makefile is not None:
				return self.commands['compile'].format(os.path.dirname(syclomatic_makefile))

			return None

		self.process(pre_process_fct=build, name="Compiling", check='converted', update='compiled')

	def execute(self, target):

		def execute_(index):
			syclomatic_makefile = self.get_makefile(self.df.loc[index, target])
			run = "program"
			with open(syclomatic_makefile) as f:
				if "run:" in f.read():
					run = "run"

			return self.commands['run'].format(os.path.dirname(syclomatic_makefile), run)

		self.process(execute_, name="Executing", check='compiled', update='executed', set_time=True, timeout=120, verbose=False)

		print(self.df)

	def get_makefile(self, input_dir):
		makefiles = glob.glob(input_dir+"/**/Makefile", recursive=True)
		if len(makefiles) > 0:
			return makefiles[0]
		return None
	
	def process(self, pre_process_fct, post_process_fct=None, name="",  timeout=0, check=None, update=None, set_time=False, verbose=False):
		total = len(self.df)

		def process(istart, istop, progress=None):

			def kill_proc(proc, idx, field, value):
				print(f'----> {self.df.loc[idx, "sycl"]} timeout ')
				self.df.loc[idx, field] = value
				proc.kill()

			for idx in range(istart, istop):
				try:
					if check is None or self.df.loc[idx, check]:
						command = pre_process_fct(idx)
						if command is not None:
							start_time = perf_counter()
							
							proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
							
							timer = Timer(timeout, kill_proc, [proc, idx, 'time', 0]) if timeout > 0 else None
							if timer is not None:
								timer.start()
							out, err = proc.communicate()
							if timer is not None:
								timer.cancel()
							if set_time:
								self.df.loc[idx, 'time'] = perf_counter() - start_time
							errcode = proc.returncode
							if errcode:
								if self.verbose:
									cprint.err(f'-----> Error while {name} {self.df.loc[idx, "syclomatic"]}')
									cprint.warn(err.decode()) 
								
							if update is not None:
								self.df.loc[idx, update] = (errcode==0)
						

						if post_process_fct is not None:
							post_process_fct(idx)

				except Exception as e:
					logging.error(e)
				with self.lock:
					if progress is not None:
						progress.update(1)

		with tqdm(total=total, desc=name.ljust(15), colour='#008888') as progress:                         
			with cf.ThreadPoolExecutor() as executor:
				workers = executor._max_workers

				chunck_size = total // workers
				futures = []
				for i in range(workers):
					istart = chunck_size*i;
					istop = chunck_size*(i+1) if i!=(workers-1) else total
					futures.append(executor.submit(process, istart, istop, progress))

				cf.wait(futures)

	def get_index(self, index, cuda_dirs, default=0):
		if index is not None:
			if not str(index).isnumeric():
				cuda_path = os.path.join(self.input_dir,f"{index}-cuda")
				if cuda_path in cuda_dirs:
					index = cuda_dirs.index(cuda_path)
				else:
					index = default
		else:
			index = default

		return index

	def plot(self):

		self.df.to_csv(self.name+'.csv', index = None, header=True)

		total = len(self.df)
		compiled = len(self.df[self.df['compiled']==True])
		executed = len(self.df[self.df['executed']==True])

		data = {
			'Total':	total,
			'Compiled':	compiled,
			'Executed':	executed
		}
		
		names = list(data.keys())
		values = list(data.values())

		plt.bar(range(len(data)), values, tick_label=names)
		plt.title(self.name.capitalize())

		plt.savefig(self.name+'.png')

		if self.visualize:
			plt.show()



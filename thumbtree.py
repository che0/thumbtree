#!/usr/bin/env python

import os, stat, sys, subprocess, shutil

class TreeThumbnailer(object):
	""" Class for creating thumbnail tree from a photo tree. """
	
	def __init__(self, max_dimensions, quality):
		self.max_dimensions = max_dimensions
		self.quality = quality
	
	@staticmethod
	def list_dir(path):
		""" Lists given directory, returning dictionary
		that has file/dir names as keys and (mode, mtime)
		as values.
		"""
		out = {}
		for f in os.listdir(path):
			st = os.lstat(os.path.join(path, f))
			out[f] = (st[stat.ST_MODE], st[stat.ST_MTIME])
		return out
	
	def refresh_file(self, source_file, target_file):
		""" Refresh file thumbnail """
		image_exts = ('.jpg', '.jpeg', '.bmp', '.png', '.gif')
		copy_exts = ('', '.mov', '.avi', '.txt', '.mp4', '.pdf')
                ignored_exts = ('.xcf', '.cr2', '.zip', '.bz2', '.xcf', '.pto', '.mk', '.exr', '.tif', '.psd', '.xml', '.mcf')
		ignored_files = ('Thumbs.db', '.DS_Store')
		
		ext = os.path.splitext(source_file)[1].lower()
		if ext in image_exts:
			self.make_thumbnail(source_file, target_file)
		elif ext in ignored_exts or os.path.basename(source_file) in ignored_files:
			print 'skipping %s' % target_file
			subprocess.check_call(['touch', target_file])
		elif ext in copy_exts:
			print 'copying %s' % target_file
			shutil.copyfile(source_file, target_file)
		else:
			raise Exception('unknown filetype: %s %s' % (ext, source_file))
	
	def make_thumbnail(self, source_file, target_file):
		""" Refresh thumbnail image. Takes paths as argument. Source exists, target does not. """
		print 'thumbnailing %s' % target_file
		call_argv = [
			'convert',
			'-size', '%sx%s' % self.max_dimensions, # set max dimensions for reading
			source_file,
			'-resize', '%sx%s>' % self.max_dimensions, # fit to this size
			'-quality', str(self.quality), # output quality
			target_file,
		]
		subprocess.check_call(call_argv)
	
	def remove_item(self, target_mode, target_path):
		""" Remove item from target tree. """
		if stat.S_ISDIR(target_mode):
			print "replacing directory: %s" % target_path
			shutil.rmtree(target_path)
			return
		
		if stat.S_ISLNK(target_mode):
			print "replacing symlink: %s" % target_path
		elif stat.S_ISREG(target_mode):
			print "replacing file: %s" % target_path
		else:
			print "replacing item: %s" % target_path
		os.unlink(target_path)
	
	def resolve_trees(self, source_path, target_path):
		""" Make target_path dir a thumbnail copy of source_path dir. """
		source = self.list_dir(source_path)
		target = self.list_dir(target_path)
		
		# go through source content
		for item_name in source:
			sitem_mode, sitem_time = source[item_name]
			sitem_path = os.path.join(source_path, item_name)
			titem_path = os.path.join(target_path, item_name) # target path
			titem = target.pop(item_name, None)
			if titem != None:
				titem_mode, titem_time = titem
			
			if stat.S_ISDIR(sitem_mode):
				# source is directory
				if titem == None:
					# target does not exist, create and resolve
					print "new directory: %s" % sitem_path
					os.mkdir(titem_path)
					self.resolve_trees(sitem_path, titem_path) # resolve recursively
				else:
					# target path exists
					if not stat.S_ISDIR(titem_mode):
						self.remove_item(titem_mode, titem_path)
						os.mkdir(titem_path)
					self.resolve_trees(sitem_path, titem_path) # resolve recursively
				
			elif stat.S_ISLNK(sitem_mode):
				# source is a symbolic link
				sitem_linksto = os.readlink(sitem_path)
				if os.path.isabs(sitem_linksto):
					print "symlink %s link to absolute path: %s" % (sitem_path, sitem_linksto)
				
				if titem == None:
					print "creating symlink: %s" % titem_path
					os.symlink(sitem_linksto, titem_path)
				else:
					if not stat.S_ISLNK(titem_mode):
						self.remove_item(titem_mode, titem_path)
						os.symlink(sitem_linksto, titem_path)
					elif os.readlink(titem_path) != sitem_linksto:
						print "updating symlink %s" % titem_path
						os.unlink(titem_path)
						os.symlink(sitem_linksto, titem_path)
				
			elif stat.S_ISREG(sitem_mode):
				# source is a regular file
				if titem == None:
					self.refresh_file(sitem_path, titem_path)
				else:
					if not stat.S_ISREG(titem_mode):
						self.remove_item(titem_mode, titem_path)
						self.refresh_file(sitem_path, titem_path)
					elif sitem_time >= titem_time:
						os.unlink(titem_path)
						self.refresh_file(sitem_path, titem_path)
			
			else:
				# weird stuff in our tree
				print "weird item in source tree: %s" % sitem_path
		# end of what's in source
		
		# go through remaining stuff in destination
		for item_name in target:
			titem_mode, _ = target[item_name]
			titem_path = os.path.join(target_path, item_name)
			if stat.S_ISDIR(titem_mode):
				print "clearing removed directory: %s" % titem_path
				shutil.rmtree(titem_path)
			else:
				print "clearing removed item: %s" % titem_path
				os.unlink(titem_path)
	
	def thumbnail_tree(self, source_path, dest_path):
		""" Make dest_path thumbnail tree of source_path. """
		if not stat.S_ISDIR(os.stat(source_path)[stat.ST_MODE]):
			raise Exception('%s is not a directory' % source_path)
		
		if not os.path.exists(dest_path):
			print 'creating destination directory: %s' % dest_path
			os.mkdir(dest_path)
		else:
			if not stat.S_ISDIR(os.stat(dest_path)[stat.ST_MODE]):
				raise Exception('%s is not a directory' % dest_path)
		
		self.resolve_trees(source_path, dest_path)

def main():
	print "%s -> %s" % (sys.argv[1], sys.argv[2])
	
	max_dim = (1920, 1200)
	quality = 88
	
	tt = TreeThumbnailer(max_dim, quality)
	tt.thumbnail_tree(sys.argv[1], sys.argv[2])

if __name__ == '__main__':
	main()

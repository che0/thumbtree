import os, stat

class TreeThumbnailer(object):
	""" Class for creating thumbnail tree from a photo tree. """
	
	@staticmethod
	def list_dir(path):
		""" Lists given directory, returning dictionary
		that has file/dir names as keys and (mode, mtime)
		as values.
		"""
		out = {}
		for f in os.listdir(path):
			st = os.stat(os.path.join(path, f))
			out[f] = (st[stat.ST_MODE], st[stat.ST_MTIME])
		return out
	
	def refresh_file(self, source_file, target_file):
		""" Refresh thumbnail image. Takes paths. """
		print 'refresh %s to %s' % (source_file, target_file)
	
	def resolve_trees(self, source_path, target_path):
		""" Make target_path dir a thumbnail copy of source_path dir. """
		source = self.list_dir(source_path)
		target = self.list_dir(target_path)
		
		# go through source content
		for sitem in source:
			smode, stime = source[sitem]
			if stat.S_ISDIR(mode):
				titem = target.pop(sitem, None)
				if titem != None:
					os.

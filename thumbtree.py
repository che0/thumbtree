#!/usr/bin/env python3

import os
import stat
import sys
import subprocess
import shutil
import logging
import tempfile
import re


IMAGE_EXTS = ('.jpg', '.jpeg', '.bmp', '.png', '.gif')
RAW_EXTS = ('.cr2', '.dng')
VIDEO_EXTS = ('.mov', '.avi', '.mp4')
COPY_EXTS = ('', '.txt', '.pdf')
IGNORED_EXTS = ('.xcf', '.zip', '.bz2', '.xcf', '.pto', '.mk', '.exr', '.tif', '.psd', '.xml', '.mcf', '.pp3')
IGNORED_FILES = ('Thumbs.db', '.DS_Store')


class TreeThumbnailer:
    """ Class for creating thumbnail tree from a photo tree. """

    def __init__(self, max_dimensions, quality):
        self.max_dimensions = max_dimensions
        self.quality = quality
        self.resize_pp3_dir = None

    def close(self):
        if self.resize_pp3_dir:
            self.resize_pp3_dir.cleanup()

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

    def raw_target(self, source_file):
        """ Returns raw thumbnail name or None if file is not raw """
        basename, ext = os.path.splitext(source_file)
        if ext.lower() in RAW_EXTS:
            return '{0}.jpg'.format(basename)
        else:
            return None

    def trashed_in_pp3(self, source_path):
        pp3 = '{}.pp3'.format(source_path)
        if os.path.isfile(pp3) and re.search(r'^InTrash=true$', open(pp3).read(), re.MULTILINE):
            return True
        else:
            return False

    def refresh_file(self, source_file, target_file):
        """ Refresh file thumbnail """

        ext = os.path.splitext(source_file)[1].lower()
        if ext in IMAGE_EXTS:
            self.make_thumbnail(source_file, target_file)
        elif ext in VIDEO_EXTS:
            self.make_video_thumbnail(source_file, target_file)
        elif ext in RAW_EXTS:
            self.make_raw_thumbnail(source_file, target_file)
        elif ext in IGNORED_EXTS or os.path.basename(source_file) in IGNORED_FILES:
            logging.info('skipping {}'.format(target_file))
            subprocess.check_call(['touch', target_file])
        elif ext in COPY_EXTS:
            logging.info('copying {}'.format(target_file))
            shutil.copyfile(source_file, target_file)
        else:
            raise Exception('unknown filetype: %s %s' % (ext, source_file))

    def get_resize_pp3(self):
        if self.resize_pp3_dir:
            return os.path.join(self.resize_pp3_dir.name, 'resize.pp3')

        self.resize_pp3_dir = tempfile.TemporaryDirectory()
        resize_pp3 = """
[Version]
AppVersion=5.2
Version=326

[Resize]
Enabled=true
AppliesTo=Cropped area
Method=Lanczos
DataSpecified=3
Width={0[0]}
Height={0[1]}
""".format(self.max_dimensions)
        pp3_path = os.path.join(self.resize_pp3_dir.name, 'resize.pp3')
        with open(pp3_path, 'w') as pp3_file:
            pp3_file.write(resize_pp3)

        return pp3_path

    def make_raw_thumbnail(self, source_file, target_file):
        logging.info('thumbnailing RAW file {}'.format(source_file))
        subprocess.check_call([
            'rawtherapee-cli',
            '-d', '-s', '-p', self.get_resize_pp3(), # default -> sidecar -> resize
            '-j{}'.format(self.quality),
            '-o', target_file,
            '-c', source_file,
        ])

    def make_video_thumbnail(self, source_file, target_file):
        logging.info('thumbnailing video file %s', source_file)
        subprocess.check_call([
            'ffmpeg',
            '-loglevel', 'error',
            '-i', source_file,
            '-c:a', 'aac',
            '-c:v', 'h264',
            '-crf', '30',
            target_file,
        ])

    def make_thumbnail(self, source_file, target_file):
        """ Refresh thumbnail image. Takes paths as argument. Source exists, target does not. """
        logging.info('thumbnailing {}'.format(target_file))
        subprocess.check_call([
            'convert',
            '-size', '{0[0]}x{0[1]}'.format(self.max_dimensions), # set max dimensions for reading
            source_file,
            '-resize', '{0[0]}x{0[1]}>'.format(self.max_dimensions), # fit to this size
            '-quality', str(self.quality), # output quality
            target_file,
        ])

    def remove_item(self, target_mode, target_path):
        """ Remove item from target tree. """
        if stat.S_ISDIR(target_mode):
            logging.info("replacing directory: {}".format(target_path))
            shutil.rmtree(target_path)
            return

        if stat.S_ISLNK(target_mode):
            logging.info("replacing symlink: {}".format(target_path))
        elif stat.S_ISREG(target_mode):
            logging.info("replacing file: {}".format(target_path))
        else:
            logging.info("replacing item: {}".format(target_path))
        os.unlink(target_path)

    def resolve_trees(self, source_path, target_path):
        """ Make target_path dir a thumbnail copy of source_path dir. """
        source = self.list_dir(source_path)
        target = self.list_dir(target_path)

        # go through source content
        regular_source_files = {}
        for item_name in source:
            sitem_mode, sitem_time = source[item_name]
            sitem_path = os.path.join(source_path, item_name)
            titem_path = os.path.join(target_path, item_name) # target path

            if stat.S_ISDIR(sitem_mode):
                # source is directory
                titem = target.pop(item_name, None)
                if titem is None:
                    # target does not exist, create and resolve
                    logging.info("new directory: {}".format(sitem_path))
                    os.mkdir(titem_path)
                    self.resolve_trees(sitem_path, titem_path) # resolve recursively
                else:
                    # target path exists
                    titem_mode, _ = titem
                    if not stat.S_ISDIR(titem_mode):
                        self.remove_item(titem_mode, titem_path)
                        os.mkdir(titem_path)
                    self.resolve_trees(sitem_path, titem_path) # resolve recursively

            elif stat.S_ISLNK(sitem_mode):
                # source is a symbolic link
                sitem_linksto = os.readlink(sitem_path)
                if os.path.isabs(sitem_linksto):
                    logging.info("symlink {0} link to absolute path: {1}".format(sitem_path, sitem_linksto))

                titem = target.pop(item_name, None)
                if titem is None:
                    logging.info("creating symlink: {}".format(titem_path))
                    os.symlink(sitem_linksto, titem_path)
                else:
                    titem_mode, _ = titem
                    if not stat.S_ISLNK(titem_mode):
                        self.remove_item(titem_mode, titem_path)
                        os.symlink(sitem_linksto, titem_path)
                    elif os.readlink(titem_path) != sitem_linksto:
                        logging.info("updating symlink {}".format(titem_path))
                        os.unlink(titem_path)
                        os.symlink(sitem_linksto, titem_path)

            elif stat.S_ISREG(sitem_mode):
                # source is a regular file, process those a bit later
                regular_source_files[item_name] = source[item_name]

            else:
                # weird stuff in our tree
                logging.info("weird item in source tree: {}".format(sitem_path))
        # end of what's in source

        # process regular files, sorting out raws and their jpegs
        for file_name in regular_source_files:
            raw_target_file = self.raw_target(file_name)
            if raw_target_file in regular_source_files:
                continue # skip raws that have their jpeg in source dir

            sitem_path = os.path.join(source_path, file_name)
            if self.trashed_in_pp3(sitem_path):
                continue

            target_name = raw_target_file or file_name
            titem_path = os.path.join(target_path, target_name) # target path

            titem = target.pop(target_name, None)
            if titem is None:
                self.refresh_file(sitem_path, titem_path)
            else:
                titem_mode, titem_time = titem
                if not stat.S_ISREG(titem_mode):
                    self.remove_item(titem_mode, titem_path)
                    self.refresh_file(sitem_path, titem_path)
                elif sitem_time >= titem_time:
                    os.unlink(titem_path)
                    self.refresh_file(sitem_path, titem_path)

        # go through remaining stuff in destination
        for item_name in target:
            titem_mode, _ = target[item_name]
            titem_path = os.path.join(target_path, item_name)
            if stat.S_ISDIR(titem_mode):
                logging.info("clearing removed directory: {}".format(titem_path))
                shutil.rmtree(titem_path)
            else:
                logging.info("clearing removed item: {}".format(titem_path))
                os.unlink(titem_path)

    def thumbnail_tree(self, source_path, dest_path):
        """ Make dest_path thumbnail tree of source_path. """
        if not stat.S_ISDIR(os.stat(source_path)[stat.ST_MODE]):
            raise Exception('{} is not a directory'.format(source_path))

        if not os.path.exists(dest_path):
            logging.info('creating destination directory: {}'.format(dest_path))
            os.mkdir(dest_path)
        else:
            if not stat.S_ISDIR(os.stat(dest_path)[stat.ST_MODE]):
                raise Exception('{} is not a directory'.format(dest_path))

        self.resolve_trees(source_path, dest_path)

def main():
    logging.getLogger().setLevel(logging.INFO)
    logging.info("{0} -> {1}".format(sys.argv[1], sys.argv[2]))

    max_dim = (1920, 1200)
    quality = 88

    tt = TreeThumbnailer(max_dim, quality)
    tt.thumbnail_tree(sys.argv[1], sys.argv[2])
    tt.close()

if __name__ == '__main__':
    main()

"""Directory syncer
Usage: python v2.py [OPTIONS] SOURCE DESTINATION
  Reads a list of shell patterns and finds all files in directory
SOURCE that match the pattern. If timestamps of files are different from
those in the index file, the file is copied to the directory DESTINATION.
  SOURCE defaults to the current working directory.
  DESTINATION must be specified.
  If an index file in not given the program will look for the file
'.sync_index' in DESTINATION. If it is not present all files will be 
copied and the file will be created.
  If a pattern file is not specified, the program will look for the
file '.sync_pattern' in SOURCE and if that is not found, all files will
'match' pattern.

Options:
 -i ..., --index=...	specify name of file that stores file information
 -p ..., --pattern=...	specify name of file that has patterns to follow
 -h, --help		show this help message
 -v, --verbose		explain what is being done
 -s			show a summary of program results
 -r			hide errors messages
"""
__author__ = "Adrian Stoll"
__date__ = "Wed Jul 31 19:35:00 2013"
__version__ = "Version 1.0"
import os, hashlib, re, glob, time, errno, shutil, sys, getopt
def logError(message):
	if not repress:
		sys.stderr.write("Error: %s\n" % (message,))
def printM(message):
	if verbose:
		sys.stdout.write("%s\n" % message)
def removeBashComment(s):
	'Takes a string and returns a string with bash comments removed'
	if '#' in s: return s[:s.index('#')].strip()
	return s.strip()
def getHash(f):
	'Takes a file object and returns md5sum of file as string of hex digits'
	h = hashlib.md5()
	try: f.seek(0,0)
	except IOError: return None
	for l in f: h.update(l)
	return h.hexdigest() 
def inDirectory(f, d):
	d = os.path.realpath(d)
	f = os.path.realpath(f)
	return os.path.commonprefix([f,d]) == d and f != d
def fixPath(path):
	return os.path.normcase(os.path.realpath(os.path.expanduser(path)))
def ensureDirectoryExists(d):
	try: os.makedirs(d)
	except OSError as exception:
		if exception.errno != errno.EEXIST: raiser
def createIndex(fileList):
	'''Takes list of files to create index of, and name of index.
	The name of each file (if it exists), its md5 sum, and last
	time of modification are recorded in the index. database is returned'''
	db = {}
	for f in fileList:
		try: i = open(f,'r')
		except IOError: logError("unable to open \"%s\"" % f)
		else:
			h = getHash(i)
			m = time.ctime(os.path.getmtime(f))
			if h and m: db[f] = (h,m)
			else: logError("unable to get info on \"%s\"" % f)
	return db
def writeIndex(db, path):
	'''writes the contents of db to file specified by path
	in format hash modification time filename. Returns 1 on
	success, None on failure'''
	try: f = open(path,'w')
	except IOError:
		logError("unable to open \"%s\"" % (path,))
		return None 
	for e in db.items():
		try: f.write("%s %s %s\n" % (e[1][0], e[1][1], e[0]))
		except IOError: logError("unable to write entry")
	f.flush()
	f.close()
	return 1
def readIndex(file):
	'''reads in file with list of hashsums, times, and filepaths.
	Returns dictionary of tuples with these elements or None'''
	try: f = open(fixPath(file),'r')
	except IOError: return None
	try:
		s = f.read()
		f.close()
	except IOError: return None
	fileList = {}
	sumRe = re.compile(r"[a-fA-F0-9]{32}")
	tsRe = re.compile(r"""^ 
			(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\ #day of week, space
			(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\ 
			#month followed by space
			[ 123]\d\ [012]\d:[0-5]\d:[0-5]\d\ [12]\d{3}
			#day of month, space, hour:minutei:sec, space, year
			$""",re.VERBOSE)
	for l in [i for i in[removeBashComment(i) for i in s.split('\n')]if i]:
		if len(l) < 59: 
			logError("invalid entry \"%s\"" % l)
			continue
		sum = l[:32]	#get hash sum
		ts = l[33:57]	#timestamp
		if not (sumRe.match(sum) and tsRe.match(ts)):
			logError("invalid entry \"%s\"" % l)
			continue
		name = l[58:].strip() 		#filename
		fileList[name] = (sum,ts)
	return fileList
def updateIndex(changedFiles,index):
	'''takes a dictionary with filenames as keys and (md5sum,timestamp)
	as values and adds of updates the values corisponding to the list
	of changed files'''
	for f in changedFiles:
		try: i = open(f,'r')
		except IOError: logError("unable to open \"%s\"" % f)
		else:
			h = getHash(i)
			m = time.ctime(os.path.getmtime(f))
			if h and m: index[f] = (h,m)
			else: logError("unable to get info on \"%s\"" % f)
def findChangedFiles(fileList,index):
	'''returns tuple with list of changed files (new or modified)
	and numbers of new, modified, and deleted/moved files'''
	list = []
	new, modified = (0,0)
	for f in fileList:
		if f in index.keys():
			m = time.ctime(os.path.getmtime(f))
			if m != index[f][1]:
				list.append(f)
				modified += 1
		else:
			list.append(f)
			new += 1
	return (list,new,modified,len(index.keys()) + new - len(fileList))
def readPatternList(file):
	'''read in file with list of patterns (think git ignore)
	and returns a list of these patterns or None if file nonexistant'''
	try: f = open(fixPath(file),'r')
	except IOError: return None
	try: s = f.read()
	except IOError: return None
	return [i for i in [removeBashComment(l) for l in s.split('\n')] if i] 
def getFileList(patterns, rootdir = os.getcwd()):
	'''Takes a list of patterns and optionally the root directory to look in
	and returns list of files that match and are in rootdir (or a subdir)
	if rootdir is invalid (ex: file not dir), cwd is used. The list of files
	returned is of their relative paths.'''
	cwd = os.getcwd()	#save for later
	rootdir = fixPath(rootdir)
	if not os.path.isdir(rootdir):
		rootdir = cwd 
	else: os.chdir(rootdir)
	list = []
	ret = {}
	for p in patterns:
		list.extend(glob.glob(fixPath(p)))
	for f in list:
		f = fixPath(f)
		if not inDirectory(f,rootdir):
			logError("file \"%s\" is not in root directory \"%s\
				\"" % (f,rootdir))
		elif os.path.isdir(f):
			list.extend([os.path.join(f,i) for i in os.listdir(f)])
		else:
			ret[f[len(rootdir)+1:]] = 1 #using dictionary prevents duplicate entries (also convert from absolute to relative path)
	os.chdir(cwd)
	return ret.keys()
def copyFilesToDirectory(fl, d):
	'''takes a list of file and copies them to the directory specified.
	metadata, such as modification time is preserved (mostly). Returns
	the number of files copied, or None if invalid destination given'''
	filesCopied = 0;
	try: ensureDirectoryExists(d)
	except OSError:
		logError("could not ensure destination \"%s\" exists." % d)
		return None
	for f in fl:
		if os.path.isdir(f): continue #ignore directories
		e = os.path.join(d, os.path.split(f)[0])
		try: ensureDirectoryExists(e)
		except OSError:
			logError("could not ensure directory \"%s\" exists" % e)
			continue
		try: shutil.copy2(f,e)
		except: logError("could not copy file \"%s\" to \"%s\"" % (f,e))
		else: filesCopied += 1
	return filesCopied
def usage():
	print __doc__
def main(argv):
	flags, longFlags  = ("i:p:hvsr", ["index=","pattern=","help","verbose"])
	index, pattern = ("","")
	global verbose
	global repress
	verbose = 0
	repress = 0
	summary = 0;
	sourceDir, destDir = (os.getcwd(),"")
	pl = []
	new, modified, removed = (0,0,0)
	try:
		opts, args = getopt.getopt(argv,flags,longFlags)
	except getopt.GetoptError:
		usage()
		sys.exit(2)
	for opt, arg in opts:
#		print "opt = %s, arg = %s" % (opt, arg)
		if opt in ("-i","--index"):
			index = arg
		elif opt in ("-p","--pattern"):
			pattern = arg
		elif opt in ("-h", "--help"):
			usage()
			sys.exit(0)
		elif opt in ("-v","--verbose"):
			verbose = 1
		elif opt == "-s":
			summary = 1
		elif opt == "-r":
			repress = 1
	al = len(args)
	if al == 0:
		logError("no destination specified... aborting")
		sys.exit(2)
	elif al == 1:
		destDir = args[0]
	elif al == 2:
		sourceDir = args[0]
		destDir = args[1]
	else:
		logError("to many paramaters... aborting")
		sys.exit(2)
	if not destDir:
		logError("no destination specified... aborting")
		sys.exit(2)
	elif destDir == sourceDir:
		logError("source and destination directory cannot be the same")
		sys.exit(2)
	if pattern: pl = readPatternList(pattern)
	if not pl: pl = ["*"]	#default to everything
	#print pl
	if not os.path.isdir(sourceDir):
		logError("source \"%s\" is not a directory" % sourceDir)
		sys.exit(2)
	print sourceDir
	fl = getFileList(pl,sourceDir)
	if not fl:
		print "not files mathcing pattern(s)"
		sys.exit()
	db = readIndex(index)
	if db:
		print "checking for modified files"
		cf = findChangedFiles(fl,db)
		new, modifed, removed = cf[1:]
		print "updating index"
		cf = cf[0]
		updateIndex(cf,db)
	else:
		print "creating index"
		db = createIndex(fl)
		cf = fl
		new = len(fl)
	if len(cf) == 0:
		print "no modified or added files"
		sys.exit()
	numC = copyFilesToDirectory(cf,destDir)
	print "%d new, %d modified, %d deleted/moved?" % (new,modified,removed)
	print "%d/%d copied" % (numC,new+modified)
	print "writing index"
	writeIndex(db,index)
if __name__ == "__main__":
	main(sys.argv[1:])

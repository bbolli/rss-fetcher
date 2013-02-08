"""basefetcher.py

This is a base class for RSS consumers.

Its remembers the timestamp of the last processed feed entry,
so only unhandled entries are processed by default.

Subclasses should implement the handle_entry(self, entry) method.
It is called with a feedparser entry dict as argument."""

import os, errno, time, pprint
import feedparser

XDG_DATA_HOME = '~/.local/share'
RSS_DATA_DIR = os.path.join(XDG_DATA_HOME, 'rss')
RSS_DATA = os.path.join(RSS_DATA_DIR, 'latest.py')


class BaseRSSFetcher:

    def __init__(self, db_file=None):
        """Initialize a new fetcher.

        These options determine its behavour:
            db_file (string, optional): the name of the database file that stores the
                timestamp os the last processed entry per feed URL
            debug (integer): the logging level
            dry_run (bool): if true, perform a dry run: no db updates
            force (bool): if true, ignore the db timestamp and process all entries
        """
        self.db_file = db_file or os.path.expanduser(RSS_DATA)
        self.debug = 0
        self.dry_run = False
        self.force = False

        self.db = {}
        self.url = None
        self.log_started = False
        try:
            os.makedirs(os.path.dirname(self.db_file))
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
        try:
            db = open(self.db_file).read()
        except (IOError, OSError):
            db = '{}'
        try:
            self.db = eval(db, {}, {})
        except Exception, e:
            self.log(repr(e))
            sys.exit(2)

    def __del__(self):
        self.close()

    def close(self):
        if not self.dry_run and self.db_file:
            data = repr(self.db).replace('), ', ',\n ') + '\n'
            try:
                open(self.db_file, 'w').write(data)
            except (IOError, OSError) as e:
                self.log('* Unable to save database: %s' % e)
            self.db_file = None

    def log(self, msg, level=0):
        if level > self.debug:
            return
        if not self.log_started:
            print time.asctime()
            if self.url:
                print self.url
            self.log_started = True
        if type(msg) in (str, unicode):
            print msg.encode('utf-8')
        else:
            pprint.pprint(msg)

    def path(self, *suffixes):
        return os.path.join(self.dest_dir, *suffixes)

    def fetch(self, url):
        self.latest_updated = self.db.setdefault(url, 0)
        self.url = url
        feed = feedparser.parse(url)
        if not hasattr(feed, 'status'):
            self.log('! feed object has no status attribute:', 1)
            return self.log(feed, 1)
        self.log(feed, 4)
        if feed.status == 301:      # permanently redirected
            self.log('* Redirect: %s\n  ==>       %s' % (url, feed.href))
        elif feed.status == 410:    # gone
            self.log('! Gone: %s' % url)
            if url in self.db:
                del self.db[url]
            return
        elif feed.status != 200:
            self.log('* Status: %d' % feed.status)
        self.new_latest = self.latest_updated
        for entry in feed.entries:
            tm = time.mktime(entry.updated_parsed)
            if not self.force and tm <= self.latest_updated:
                self.log('! Old entry, already looked at earlier: %s' % entry.title, 1)
            elif self.latest_updated < tm:
                if self.handle_entry(entry):
                    self.log(entry.title)
                    self.new_latest = max(self.new_latest, tm)
                    self.log('* Updating latest date to %s' % time.ctime(tm), 1)
        self.db[url] = self.new_latest
        self.url = None

    def handle_entry(self, entry):
        raise NotImplementedError('please override handle_entry()')

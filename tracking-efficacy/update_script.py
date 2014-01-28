#!/usr/bin/python

"""Many thanks to Tracy Chou for https://github.com/triketora/women-in-software-eng/blob/master/update_script.py and by association this blog post:
http://www.mattcutts.com/blog/write-google-spreadsheet-from-python/"""

import argparse
import datetime
import re

from gdata.spreadsheet import service as ss_service

SS_KEY = 'needed'
WORKSHEET_ID = 'needed'

FIXED_ON_MC_QUERY = "https://bugzilla.mozilla.org/buglist.cgi?bug_status=RESOLVED&bug_status=VERIFIED&bug_status=CLOSED&f1=target_milestone&f2=target_milestone&j_top=ORo1=equals&o2=equals&product=Core&product=Firefox&product=Firefox%20for%20Android&product=Toolkit&v1=mozilla{{CURRENT_VERSION}}&v2=Firefox%20{{CURRENT_VERSION}}&limit=0"
TRACKING_PLUS_FULL_LIST_QUERY = "https://bugzilla.mozilla.org/buglist.cgi?f1=cf_tracking_firefox{{CURRENT_VERSION}}&limit=0&o1=equals&v1=%2B"
TRACKING_PLUS_FIXED = "https://bugzilla.mozilla.org/buglist.cgi?f1=cf_tracking_firefox{{CURRENT_VERSION}}&o1=equals&o2=anywords&f2=cf_status_firefox{{CURRENT_VERSION}}&v1=%2B&v2=fixed%2Cverified%2Cunaffected&limit=0"
TRACKED_LEFT_UNFIXED = "https://bugzilla.mozilla.org/buglist.cgi?f1=cf_tracking_firefox{{CURRENT_VERSION}}&o1=equals&o2=anywords&f2=cf_status_firefox{{CURRENT_VERSION}}&v1=%2B&v2=affected%2Cwontfix&limit=0"
# get the from and to as YYYY-MM-DD - easy
TOTAL_NOMS = "https://bugzilla.mozilla.org/buglist.cgi?chfield=cf_tracking_firefox{{CURRENT_VERSION}}&chfieldfrom={{CURRENT_CYCLE_FROM}}&chfieldto={{CURRENT_CYCLE_TO}}&limit=0"
# might need to tweak this for new keywords breakdown (do platform separations?)
TRACKED_CRASHERS = "https://bugzilla.mozilla.org/buglist.cgi?keywords=crash%2C%20topcrash%2C%20&f1=cf_tracking_firefox{{CURRENT_VERSION}}&keywords_type=anywords&o1=equals&v1=%2B&limit=0"

ss_client = None

def init_ss_client(email, password):
    global ss_client
    if ss_client is None:
        ss_client = ss_service.SpreadsheetsService()
        ss_client.email = email
        ss_client.password = password
        ss_client.source = 'Update Script'
        ss_client.ProgrammaticLogin()

def _print_line_skip_warning(line):
    print 'Warning... skipping line:\n\t%s\n' % line

row_key_pattern = '\[(?P<row_key>\w+\]'
row_key_prog = re.compile(row_key_pattern)

def _extract_row_key_from_data_line(line):
    row_key = None
    m = row_key_prog.match(line)
    if m and m.group('row_key'):
        row_key = m.group('row_key')
    return row_key

col_keys = (
    'fixed_on_mc',
    'tracking_plus_full_list',
    'tracking_plus_fixed',
    'tracking_left_unfixed',
    'total_noms',
    'tracked_topcrash'
    )

# Poll the query urls above
# New api?

# Insert the resulting bug counts for each into spreadsheet
# check refreshed data?  pull the chart somehow?




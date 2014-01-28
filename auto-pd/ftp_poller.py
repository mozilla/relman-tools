#!/usr/bin/env python
"""

A script for automated polling of ftp releases and updating product-details
as well as the mozilla.com svn externals that rely on a product-details revision
to populate our download buttons on release channel web pages

"""

import ftplib
import socket
import sys
from time import strftime, strptime, ctime
from subprocess import Popen, PIPE, STDOUT
import os
import re
import json
import smtplib
from copy import deepcopy
from argparse import ArgumentParser

# put a local_config.py file in your working dir with the following:
# TOADDRS = ['email@email.com',]
# REPLY_TO_EMAIL = 'email@email.com'
from local_config import *

# To run this you need to have checked out in your HOME dir:
# svn co svn+ssh://'youremail'@svn.mozilla.org/libs/product-details product-details
# svn co svn+ssh://'youremail'@svn.mozilla.org/projects/mozilla.com mozilla.com
# https://github.com/mozilla/bztools where you have a config file in scripts/configs/config.json
# 
# Also should have in the same dir as the script a file 
# for each version and current release number:
# eg:   firefox.beta.prev contains 24.0b9
#       mobile.beta.prev contains 24.0b4
#       firefox.esr.prev contains 24.2.0esr
#       firefox.release.prev contains 26.0.1

# BUGS BUGS BUGS BUGS BUGS BUGS BUGS
# NEED TESTS - this doesn't handle ESR version bumped well
# trim off 'esr' when searching firefoxDetails
# check that the current version is not already in history/{firefox, mobile} file
# currently finds 25.0 both in main releases AND in dot releases, so duplicates info
# also on dot releases, the 'replace' in Details file ends up as 25.0.1.1 which is probably
# because of replacing just 25.0 and it contains 25.0.1 so we end up with 25.0.1.1
# bug: dot releases means history line for a new GA release goes in the wrong section of history

HOME = os.environ['HOME']
HOST = 'ftp.mozilla.org'
PATH = '/pub/mozilla.org/%s/releases/'
PD_DIR = '%s/product-details' % HOME
MZ_DIR = '%s/mozilla.com' % HOME
BZ_TOOLS = '%s/bztools' % HOME
PRODUCTS = ['firefox', 'mobile']
CHANNELS = {
    'beta' : {
        'prev': '',
        'current': '',
        'release_date': '',
        'update' : False
    },
    'release' : {
        'prev': '',
        'current': '',
        'release_date': '',
        'update' : False
    },
    'esr' : {
        'prev': '',
        'current': '',
        'release_date': '',
        'update' : False
    },
}

# Email settings
REPLY_TO_EMAIL = REPLY_TO_EMAIL
SMTP = 'smtp.mozilla.org'
CONFIG_JSON = BZ_TOOLS + "/scripts/configs/config.json"
config = json.load(open(CONFIG_JSON, 'r'))
subject = None
toaddrs = TOADDRS

def run(cmd):
    p = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
    return p.stdout.read()

def validate_month(m):
    m1 = strptime(m, "%b")
    m2 = strptime(ctime().split()[1], "%b")
    if strftime("%m", m1) == strftime("%m", m2):
        return True
    else:
        return False

def send_mail(toaddr, options):
    message = ("From: %s\r\n" % options['username']
        + "To: %s\r\n" % toaddr
        + "CC: %s\r\n" % options['cclist']
        + "Reply-To: %s\r\n" % REPLY_TO_EMAIL
        + "Subject: %s\r\n" % options['subject']
        + "\r\n"
        + options['body'])

    server = smtplib.SMTP_SSL(SMTP, 465)
    server.set_debuglevel(1)
    server.login(options['username'], options['password'])
    # note: toaddrs is required for transport agents, the msg['To'] header is not modified
    server.sendmail(options['username'], toaddrs, message)
    server.quit()

def file_replace(fname, pat, s_after):
    try:
        with open(fname) as f:
            if not any(re.search(pat, line) for line in f):
                print pat, "not found in", fname
                return # pattern does not occur in file so we are done.
        print pat, "found in", fname, "replacing with", s_after
        with open(fname) as f:
            out_fname = fname + ".tmp"
            out = open(out_fname, "w")
            for line in f:
                out.write(re.sub(pat, s_after, line))
            out.close()
            os.rename(out_fname, fname)

    except IOError:
        print fname, "does not exist"
        return

def file_addline(fname, pat, additional_line):
    try:
        with open(fname) as f:
            if not any(re.search(pat, line) for line in f):
                print pat, "not found in", fname
                return # pattern does not occur in file so we are done.
        with open(fname) as f:
            out_fname = fname + ".tmp"
            out = open(out_fname, "w")
            for line in f:
                if re.search(pat, line):
                    print pat, "found in", fname, "adding entry: ", additional_line
                    out.write(re.sub(line, line, line + additional_line))
                else:
                    out.write(line)
            out.close()
            os.rename(out_fname, fname)

    except IOError:
        print fname, "does not exist"
        return

def main():
    parser = ArgumentParser(__doc__)
    parser.set_defaults(
        products = [],
    )
    parser.add_argument("-p", "--product", dest="product", action="append",
            help="a product directory in ftp and also in the product-details")
    parser.add_argument("-d", "--dryrun", dest="dryrun", action="store_true",
            help="test the ftp results without updating the product-details or making commits to repos")

    options, args = parser.parse_known_args()

    if options.products == []:
        options.products = PRODUCTS

    working_dir = os.getcwd() + "/"

    # move to the releases dir for each product
    for product in PRODUCTS:
        try:
            # Open ftplib connection
            ftp = ftplib.FTP(HOST)
            #ftp.login()
        except (socket.error, socket.gaierror):
            print 'cannot reach %s' % HOST
            sys.exit(1)
        print "Connected to FTP server"

        try:
            ftp.login('anonymous','')
        except ftplib.error_perm:
            print 'cannot login anonymously'
            ftp.quit()

        print "Success! Logged on to the FTP server"

        channels = deepcopy(CHANNELS)
        print "\n===========  %s Output ============\n" % product.capitalize()
        ftp_path = PATH % product
        # might need a try/catch here for incorrect product input from users
        ftp.cwd(ftp_path)
        # get the dates from the files
        data = []
        ftp.retrlines('LIST', data.append)
        datelist = []
        dirlist = []
        for line in data:
            # split the file info
            col = line.split()
            # print "DEBUG col[8]: %s" % col[8]
            if col[8][0].isdigit() and "funnelcake" not in col[8]:
                if ':' in col[7]:
                    if validate_month(col[5]) == True:
                        d = [ctime().split()[-1],]
                        datestr = '-'.join(line.split()[5:7] + d)
                else:
                    datestr = '-'.join(line.split()[5:8])
                date = strptime(datestr, '%b-%d-%Y')
                datelist.append(date)
                dirlist.append(col[8])
        # put together the dates, directory names
        combo = zip(datelist, dirlist)
        dated_dirnames = dict(combo)

        ### find the most current
        for key in sorted(dated_dirnames.iterkeys(), reverse=False):
            #print "DEBUG: Running: %s" % dated_dirnames[key]
            if 'b' in dated_dirnames[key]:
                channels['beta']['current'] = dated_dirnames[key]
                channels['beta']['release_date'] = strftime('%Y-%m-%d', key)
            if product == 'firefox' and 'esr' in dated_dirnames[key]:
                #print "DEBUG: %s" % dated_dirnames[key]
                channels['esr']['current'] = dated_dirnames[key]
                channels['esr']['release_date'] = strftime('%Y-%m-%d', key)
            if 'b' not in dated_dirnames[key] and 'esr' not in dated_dirnames[key]:
                channels['release']['current'] = dated_dirnames[key]
                channels['release']['release_date'] = strftime('%Y-%m-%d', key)

        # Open the prev_version files -- TODO if no file, abort & send message saying it's missing
        for c in channels.keys():
            print "Current %s version is %s" % (c, channels[c]['current'])
            print "Looking for %s.%s.prev file" % (product, c)
            # read prev_version from file
            for files in os.listdir(working_dir):
                if ("%s.%s" % (product, c)) in files:
                    f = open(working_dir + files)
                    channels[c]['prev'] = f.read().strip()
                    print "Previous %s version was %s" % (c, channels[c]['prev'])
            ## workaround for beta
            if c == 'beta':
                if channels[c]['prev'] is not '':
                    v = channels[c]['current'].split('b')
                    vp = channels[c]['prev'].split('b')
                    if int(v[0].strip('.0')) == int(vp[0].strip('.0')):
                        if int(v[1]) > int(vp[1]):
                            channels[c]['update'] = True
                            print "the %d > %d" % (int(v[1]), int(vp[1]))
                    elif int(v[0].strip('.0')) > int(vp[0].strip('.0')):
                        channels[c]['update'] = True
                        print "the %d > %d" % (int(v[0].strip('.0')), int(vp[0].strip('.0')))
                if channels[c]['update'] == True:
                    print "Update %s! %s > %s" % (c, channels[c]['current'], channels[c]['prev'])
                else:
                     print "No update for %s" % c
            ## workaround for esr
            elif c == 'esr':
                if channels[c]['prev'] is not '' and int(channels[c]['current'].split('.')[1]) > int(channels[c]['prev'].split('.')[1]):
                    channels[c]['update'] = True
                    print "Update %s! %s > %s" % (c, channels[c]['current'], channels[c]['prev'])
                else:
                     print "No update for %s" % c    
            # Checking here for a dot release
            elif c == 'release':
                pr = int(len(channels[c]['prev'].split('.')))
                cu = int(len(channels[c]['current'].split('.')))
                if cu == 3 and pr == 2:
                    #print "DEBUG: We have a dot release, right? cur: %d prev: %d" % (cu, pr)
                    channels[c]['update'] = True
                    print "Update %s! %s > %s" % (c, channels[c]['current'], channels[c]['prev']) 
                else:
                    print "Not dealing with a dot release, carry on"     
                    if channels[c]['prev'] is not '' and channels[c]['current'] > channels[c]['prev']:
                        channels[c]['update'] = True
                        print "Update %s! %s > %s" % (c, channels[c]['current'], channels[c]['prev'])
            else:
                print "No update for %s" % c

        ### push to product details
        os.chdir(PD_DIR)

        # update the checkout of product-details
        output = "Updating checkout of product-details: " + run("svn up")

        # search for line with prev version & append to both pd and history files
        pd_file = '%sDetails.class.php' % product
        history_file = 'history/%sHistory.class.php' % product

        for c in channels.keys():
            if channels[c]['update'] == True:
                # process pd first & replace with new version
                file_replace(pd_file, channels[c]['prev'], channels[c]['current'])
                # in history file add in a new line like '24.0b7' => '2013-08-30'
                additional_line = "\t\t'%s' => '%s',\n" % (channels[c]['current'], channels[c]['release_date'])
                file_addline(history_file, channels[c]['prev'], additional_line)

                # update the prev file for next run
                for files in os.listdir(working_dir):
                    if ("%s.%s" % (product, c)) in files:
                        f = open(working_dir + files, 'w')
                        f.write(channels[c]['current'])
                        f.close()
                        print "Updated %s.%s.prev" % (product, c)

        # run export_json.php
        cmds = ["./export_json.php", "svn status"]
        for cmd in cmds:
            output += run(cmd)
        
        # only push to svn if there are modified .php files
        if ".php" in output:
            inp = raw_input('There are modified files to be pushed - go ahead with push?  Y/n: ')
            if inp == 'Y' or inp == 'y':
                cmd = "svn ci -m 'Automated bump of product-details'"
                commit_msg = run(cmd)
                print "OUTPUT FROM COMMITTING TO p-d: %s" % commit_msg
                # clean off whitespace, newlines, then take the version number
                svn_version = commit_msg.strip().rstrip('.').split()[-1]
                print "Updated SVN version is: %s" % svn_version
                output += commit_msg
            else:
                svn_version = None
                output += "No push initiated, uncommitted changes in the repo - go take a look if you want."
        else:
            svn_version = None
            output += "No changes in 'svn status', nothing will be pushed"

        # if we pushed p-d changes, update mozilla.com svn:externals
        if svn_version is not None and svn_version.isdigit():
            # update the checkout - specifically tags/{stage,production}/includes
            os.chdir(MZ_DIR)
            output += "Updating mozilla.com: " + run("svn up tags")
            # replace the svn_version number in each of those files
            svn_cmd = "svn propset svn:externals"
            pd_url = "http://svn.mozilla.org/libs/product-details"
            cert_url = "http://svn.mozilla.org/libs/certs"
            for path in ['tags/stage/includes', 'tags/production/includes']:
                # Write the externals to a temp file, then pass that to svn propset
                filename = os.getcwd() + '/temp_properties.txt'
                f = open(filename, 'w')
                f.write('product-details -r%s %s\n' % (svn_version, pd_url))
                f.write('certs %s' % cert_url)
                f.close()
                cmd = '%s -F %s %s' % (svn_cmd, filename, path)
                output += run(cmd)

            output += "svn:externals diff: " + run("svn diff")
            # push the changes to mozilla.com
            inp = raw_input("Check the modifications to svn:externals and say if you want to push Y/n: ")
            if inp == 'Y' or inp == 'y':
                cmd = "svn ci -m 'Automated bump of svn:externals' tags"
                output += run(cmd)
            else:
                output += "Didn't push the svn:externals change, uncommitted changes in the mozilla.com repo, go take a look"
        if svn_version is not None and not svn_version.isdigit():
            output += "[ALERT] something went wrong with grabbing SVN version, need to push p-d update to mozilla.com"

        # all the outputs go to the email now
        body = output

        # Send email to relman to notify completion
        options = {
            "username": config['ldap_username'],
            "password": config['ldap_password'],
            "subject": "Automated Update: %s product-details" % product.capitalize(),
            "body": body,
            "cclist": "",
            "toaddrs": toaddrs
        }

        for email in toaddrs:
            print "Sending mail to %s" % email
            send_mail(email, options)

if __name__ == '__main__':
    main()
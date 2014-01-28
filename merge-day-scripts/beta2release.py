#!/usr/bin/python

"""A merge day helper script for Beta-->Release mogration to go along with https://wiki.mozilla.org/Release_Management/Merge_Documentation"""

import urllib2
import os
import re
import subprocess
from subprocess import call
import datetime
import time

def run(cmd):
    try:
        print "Run Command: "
        call('echo ' + cmd, shell=True)
        call(cmd, shell=True)
    except:
        print "Unexpected error: cmd = |%s|" % cmd
        raise

def getTemplateValue(url):
    version_regex = re.compile(".*<p>(.*)</p>.*")
    template_page = urllib2.urlopen(url).read().replace('\n', '')
    parsed_template = version_regex.match(template_page)
    return parsed_template.groups()[0]

def file_replace(fname, pat, s_after):
    try:
        with open(fname) as f:
            if not any(re.search(pat, line) for line in f):
                 print pat, "not found in", fname
                 return False # pattern does not occur in file so we are done.
        with open(fname) as f:
            out_fname = fname + ".tmp"
            out = open(out_fname, "w")
            for line in f:
                out.write(re.sub(pat, s_after, line))
            out.close()
            os.rename(out_fname, fname)
        return True

    except IOError:
        print fname, "does not exist"
        return False


def get_user_input():

    #Reading Version number
    version = raw_input("Enter the current Release Version ( eg : 24.0 , including a chemspill version if exists) \n")
    print "you entered ", version
    hg_user = raw_input("Enter the mercurial user name in the form \"username <email@mozilla.com>\" you will use to commit changes\n")
    print "the username you entered is", hg_user
    return version,hg_user


def get_rev(repo):
    try:
        rev = subprocess.check_output('hg id -R ' + repo + ' -i -r default', shell=True)
        return rev.rstrip()
    except:
        print "get_rev: Unexpected error"
        raise

def tag_repo(repo, tag, rev, user):
    cmd = 'hg tag -R ' + repo  + ' -r ' + rev + ' -u ' + user + ' -m ' +'" Added tag ' + tag + ' for changeset CLOSED TREE a=release " ' + tag
    run(cmd)

def commit_repo(repo, user, old_head, new_head):
    print " Commiting mozilla repo " + repo
    # "Merge" the old head, rather than closing it, to avoid
    # non-fastforward issues in vcs-sync
    cmd = 'hg -R %s debugsetparents %s %s' % (repo, new_head, old_head)
    run(cmd)
    cmd = 'hg -R %s commit -m "Merging old head via |hg debugsetparents %s %s|. CLOSED TREE a=release" -u %s' % (repo, new_head, old_head, user)
    run(cmd)

def pull_up_repo(repo_beta, repo_release):
    print "pulling all changes from mozilla-beta into into mozilla-release\n"
    cmd = 'hg -R ' + repo_release  + ' pull ' + repo_beta
    run(cmd)
    print "updating mozilla-release\n"
    cmd = 'hg -R '+ repo_release + ' up -C default'
    run(cmd)

def main():
    #Clone Repos
    cmd = 'hg clone http://hg.mozilla.org/releases/mozilla-release'
    run(cmd)
    cmd = 'hg clone http://hg.mozilla.org/releases/mozilla-beta'
    run(cmd)
    mozilla_release = "./mozilla-release/"
    mozilla_beta = "./mozilla-beta/"

    version, hg_user = get_user_input()
    user_input = raw_input("Enter yes to begin with beta -> release merge day changes or no to exit\n")
    if user_input.lower() != "yes":
        print "Exiting now\n"
        return

    #Getting version numbers
    beta_rev = get_rev(mozilla_beta)
    release_rev = get_rev(mozilla_release)

    #Calculating tags
    now = datetime.datetime.now()
    date = now.strftime("%Y%m%d")
    release_base_tag = "RELEASE_BASE_" + date
    release_tag = "FIREFOX_RELEASE_" + version

    #Tagging
    print "RUNNING: tag_repo(%s, %s, %s, %s)" % (mozilla_beta, release_base_tag, beta_rev, hg_user)
    tag_repo(mozilla_beta, release_base_tag, beta_rev, hg_user)
    print "You have finished tagging mozilla-beta, now go ahead and push the mozilla-beta repo\n"
    time.sleep(30)
    user_input1 = raw_input("Enter yes to continue if you have finished pushing mozilla-beta\n")
    if  user_input1.lower() != "yes" :
        print "Exiting now\n"
        return
    print "RUNNING: tag_repo(%s, %s, %s, %s)" % (mozilla_beta, release_base_tag, beta_rev, hg_user)
    tag_repo(mozilla_release, release_tag, release_rev, hg_user)

    #Commit,pull and update
    mozilla_release_revision = get_rev(mozilla_release)
    print "MOZILLA_RELEASE_REVISION = " + mozilla_release_revision
    mozilla_beta_revision = get_rev(mozilla_beta)
    print "MOZILLA_BETA_REVISION = " + mozilla_beta_revision
    print "RUNNING: pull_up_repo(%s, %s)" % (mozilla_beta, mozilla_release)
    pull_up_repo(mozilla_beta, mozilla_release)
    print "RUNNING: commit_repo(%s, %s, %s, %s)" % (mozilla_release, hg_user, mozilla_release_revision, mozilla_beta_revision)
    commit_repo(mozilla_release, hg_user, mozilla_release_revision, mozilla_beta_revision)


#Edit desktop config

    raw_input("If you are ready to start with mozconfig changes, hit 'return' to continue...")

    if not file_replace(mozilla_release+"browser/confvars.sh", "ACCEPTED_MAR_CHANNEL_IDS=firefox-mozilla-beta,firefox-mozilla-release", "ACCEPTED_MAR_CHANNEL_IDS=firefox-mozilla-release"):
        print "Failed to replace channel ids in desktop config"

    if not file_replace(mozilla_release+"browser/confvars.sh", "MAR_CHANNEL_ID=firefox-mozilla-beta", "MAR_CHANNEL_ID=firefox-mozilla-release"):
        print "Failed to replace MAR_CHANNEL_ID in desktop config"

#Edit mobile mozconfigs

    release_branding_dirs = ["mobile/android/config/mozconfigs/android/","mobile/android/config/mozconfigs/android-armv6/","mobile/android/config/mozconfigs/android-x86/"]
    release_branding_files = ["release","l10n-release","l10n-nightly","nightly"]

    for bbd in release_branding_dirs:
        for bbf in release_branding_files:
            if not file_replace(mozilla_release+bbd+bbf, "ac_add_options --with-branding=mobile/android/branding/beta", "ac_add_options --with-branding=mobile/android/branding/official"):
                print "Failed to replace edots relating to Branding dir's in mobile mozconfig"

    print("Now, go edit any mozilla-release/browser/locales/shipped-locales file if you need to remove some beta locales (eg: mn, sw)")
    time.sleep(10)
    raw_input("Hit 'return' to continue to diff's ...")
    cmd = 'hg diff -R '+ mozilla_release
    run(cmd)
    raw_input("if the diff looks good hit return to continue to commit")
    cmd = 'hg commit -R '+ mozilla_release + ' -u ' + hg_user +' -m "Updating configs CLOSED TREE a=release ba=release"'
    run(cmd)

    raw_input("Go ahead and push mozilla-release changes and you are done.")

if __name__ == "__main__":
    main()





#!/usr/bin/python

"""A merge day helper script to go along with https://wiki.mozilla.org/Release_Management/Merge_Documentation"""

import urllib2
import os
import re
import sys
import subprocess
from subprocess import call

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
                return # pattern does not occur in file so we are done.
    
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

#=========================================================================================================#

mozilla_central =  "./mozilla-central/"
mozilla_aurora =    "./mozilla-aurora/"
mozilla_beta =      "./mozilla-beta/"

beta_version =      getTemplateValue("https://wiki.mozilla.org/Template:BETA_VERSION")
aurora_version =    getTemplateValue("https://wiki.mozilla.org/Template:AURORA_VERSION")
central_version =   getTemplateValue("https://wiki.mozilla.org/Template:CENTRAL_VERSION")
next_version =      getTemplateValue("https://wiki.mozilla.org/Template:NEXT_VERSION")

weave_version =     str(int(central_version)+2)
next_weave_version =    str(int(weave_version)+1)

# mozilla-central
## Pull,Update & Tag
call('hg pull -R '+ mozilla_central, shell=True)
call('hg up -R '+mozilla_central, shell=True)
mozilla_central_tag = "FIREFOX_AURORA_"+central_version+"_BASE"
print mozilla_central_tag
call('hg -R ' + mozilla_central + ' tag ' + mozilla_central_tag , shell=True)
raw_input("Latest mozilla-central has been pulled, updated and tagged...")
raw_input("> version-bump mozilla-central (hit 'return' to proceed) <")

## version bump
central_version_files = ["browser/config/version.txt", "config/milestone.txt", "mobile/android/confvars.sh", "b2g/confvars.sh", "js/src/config/milestone.txt"]

for avf in central_version_files:
    file_replace(mozilla_central+avf, central_version+".0a1$", next_version+".0a1")

file_replace(mozilla_central+"xpcom/components/Module.h", central_version+";$", next_version+";") 
file_replace(mozilla_central+"services/sync/Makefile.in", "\."+weave_version+"\.", "."+next_weave_version+".")

print("Verify the diff below..")
call('hg diff -R '+ mozilla_central , shell=True)
raw_input("if the diff looks good hit return to continue to commit")
call('hg -R '+ mozilla_central +' commit -m \"Merging in version bump NO BUG\"',shell=True)
call('hg out -R'+ mozilla_central , shell=True)
raw_input("Go ahead and push mozilla-central...and continue to mozilla-aurora to mozilla-beta uplift ")



# mozilla-beta
##tag mozilla-aurora, close & tag mozilla-beta
raw_input("Tagging mozilla-aurora, hit return to continue")
mozilla_aurora_tag = "FIREFOX_BETA_"+aurora_version+"_BASE"
call('hg -R '+ mozilla_aurora +' tag '+ mozilla_aurora_tag  + ' -m "Tagging for mozilla-aurora->mozilla-beta uplift CLOSED TREE DONTBUILD" ', shell=True)
call('hg out -R '+ mozilla_aurora , shell=True)
mozilla_beta_rev = subprocess.check_output('hg id -R %s -i -r default' % mozilla_beta, shell=True)
raw_input("review and push..")


raw_input("Tagging mozilla-beta")
mozilla_beta_tag = "FIREFOX_BETA_"+beta_version+"_END"
call('hg tag -R '+ mozilla_beta + ' -m "Tagging end of BETA24 CLOSED TREE DONTBUILD" '+ mozilla_beta_tag , shell=True)
call('hg -R '+ mozilla_beta +' commit --close-branch -m "closing old head CLOSED TREE DONTBUILD"', shell=True)
call('hg out -R '+ mozilla_beta, shell=True)
raw_input("review and push..")

#### Pull from Aurora into Beta ###
print mozilla_aurora_tag
#call('hg -R'+ mozilla_beta +' pull -u -r '+ mozilla_aurora_tag +' http://hg.mozilla.org/releases/mozilla-aurora', shell=True)
call('hg -R'+ mozilla_beta +' pull -r '+ mozilla_aurora_tag +' http://hg.mozilla.org/releases/mozilla-aurora', shell=True)
call('hg -R'+ mozilla_beta +' up -C', shell=True)
mozilla_aurora_rev = subprocess.check_output('hg id -R %s -i -r default' % mozilla_beta, shell=True)
call('hg -R %s hgdebugsetparents %s %s' % (mozilla_beta, mozilla_aurora_rev, mozilla_beta_rev), shell=True)
call('hg -R %s commit -m "Merging old head via |hg debugsetparents %s %s|. CLOSED TREE DONTBUILD"' % (mozilla_beta, mozilla_aurora_rev, mozilla_beta_rev), shell=True)
raw_input("> you have finished pulling aurora into mozilla_beta (hit 'return' to proceed to next step : version bump) <")

## version bump
beta_version_files = central_version_files

for avf in beta_version_files:
    file_replace(mozilla_beta+avf, aurora_version+".0a2$", aurora_version+".0")
    
### Diff and Commit
raw_input("Verify the below diff's for version bumps, hit return to commit if everthing looks good ")
call('hg diff -R'+mozilla_beta, shell=True)
call('hg -R '+ mozilla_beta +' commit -m "Merging in version bumps NO BUG CLOSED TREE ba=release"',shell=True)
call('hg out -R'+ mozilla_beta , shell=True)

## branding changes
file_replace(mozilla_beta+"browser/confvars.sh", "MOZ_BRANDING_DIRECTORY=browser/branding/aurora", "MOZ_BRANDING_DIRECTORY=browser/branding/nightly")
file_replace(mozilla_beta+"browser/confvars.sh", "ACCEPTED_MAR_CHANNEL_IDS=firefox-mozilla-aurora", "ACCEPTED_MAR_CHANNEL_IDS=firefox-mozilla-beta,firefox-mozilla-release")
file_replace(mozilla_beta+"browser/confvars.sh", "MAR_CHANNEL_ID=firefox-mozilla-aurora", "MAR_CHANNEL_ID=firefox-mozilla-beta")

beta_branding_dirs = ["mobile/android/config/mozconfigs/android/", "mobile/android/config/mozconfigs/android-armv6/", "mobile/android/config/mozconfigs/android-x86/", "mobile/android/config/mozconfigs/android-noion/"]
beta_branding_files = ["debug","l10n-nightly","nightly"]

for bbd in beta_branding_dirs:
    for bbf in beta_branding_files:
        file_replace(mozilla_beta+bbd+bbf, "ac_add_options --with-branding=mobile/android/branding/aurora", "ac_add_options --with-branding=mobile/android/branding/beta")
        

file_replace(mozilla_beta+"mobile/xul/config/mozconfigs/android/debug", "ac_add_options --with-branding=mobile/xul/branding/aurora", "ac_add_options --with-branding=mobile/xul/branding/beta")

file_replace(mozilla_beta+"mobile/xul/config/mozconfigs/android/nightly", "ac_add_options --enable-js-diagnostics", "")
file_replace(mozilla_beta+"mobile/xul/config/mozconfigs/android/nightly", "ac_add_options --enable-application=mobile", "ac_add_options --enable-application=mobile/xul")
file_replace(mozilla_beta+"mobile/xul/config/mozconfigs/android/nightly", "ac_add_options --with-branding=mobile/xul/branding/aurora", "ac_add_options --with-branding=mobile/xul/branding/beta")


raw_input("Verify the below diff's for branding changes, hit return to commit if everthing looks good ")
call('hg -R '+ mozilla_beta +' commit -m "Merging in branding changes NO BUG CLOSED TREE ba=release"',shell=True)
call('hg out -R '+ mozilla_beta , shell=True)

raw_input("continue to the wiki to do the L10n changes+commits and do the final push of mozilla-beta")

# mozilla-aurora
print("Tagging mozilla-aurora...")
mozilla_aurora_old_tag = "FIREFOX_AURORA_"+aurora_version+"_END"
#call('hg tag -R'+ mozilla_aurora +' -m "Tagging for mozilla-central->mozilla-aurora uplift CLOSED TREE" '+ mozilla_aurora_old_tag , shell=True)
call('hg -R '+ mozilla_aurora +' commit --close-branch -m "closing old head CLOSED TREE DONTBUILD" ', shell=True)
call('hg out -R'+ mozilla_aurora , shell=True)
mozilla_aurora_rev = subprocess.check_output('hg id -R %s -i -r default' % mozilla_aurora, shell=True)
raw_input("Review and do a push of mozilla-aurora")
raw_input("hit enter to Pull from m-c into Aurora ")
print mozilla_central_tag
#call('hg -R '+ mozilla_aurora +' pull -u -r ' + mozilla_central_tag + ' http://hg.mozilla.org/mozilla-central ',shell=True)
call('hg -R '+ mozilla_aurora +' pull -r ' + mozilla_central_tag + ' http://hg.mozilla.org/mozilla-central ',shell=True)
call('hg -R'+ mozilla_aurora +' up -C', shell=True)
mozilla_central_rev = subprocess.check_output('hg id -R %s -i -r default' % mozilla_aurora, shell=True)
call('hg -R %s hgdebugsetparents %s %s' % (mozilla_aurora, mozilla_central_rev, mozilla_aurora_rev), shell=True)
call('hg -R %s commit -m "Merging old head via |hg debugsetparents %s %s|. CLOSED TREE DONTBUILD"' % (mozilla_aurora, mozilla_central_rev, mozilla_aurora_rev), shell=True)

raw_input("> version-bump mozilla-aurora (hit 'return' to proceed) <")

## version bumps
aurora_version_files = central_version_files

for avf in aurora_version_files:
    file_replace(mozilla_aurora+avf, central_version+".0a1$", central_version+".0a2")


call('hg diff -R'+mozilla_aurora, shell=True)

raw_input("Above is the diff on version bumps, hit return to proceed with commit")
call('hg -R '+ mozilla_aurora +' commit -m "Merging in version bump NO BUG CLOSED TREE"',shell=True)
call('hg out -R'+mozilla_aurora, shell=True)

raw_input("Hit continue to move onto branding changes...")

## branding changes
file_replace(mozilla_aurora+"browser/confvars.sh", "MOZ_BRANDING_DIRECTORY=browser/branding/nightly", "MOZ_BRANDING_DIRECTORY=browser/branding/aurora")
file_replace(mozilla_aurora+"browser/confvars.sh", "ACCEPTED_MAR_CHANNEL_IDS=firefox-mozilla-central", "ACCEPTED_MAR_CHANNEL_IDS=firefox-mozilla-aurora")
file_replace(mozilla_aurora+"browser/confvars.sh", "MAR_CHANNEL_ID=firefox-mozilla-central", "MAR_CHANNEL_ID=firefox-mozilla-aurora")

aurora_branding_dirs = beta_branding_dirs
aurora_branding_files = beta_branding_files

for abd in aurora_branding_dirs:
    for abf in aurora_branding_files:
        file_replace(mozilla_aurora+abd+abf, "ac_add_options --with-branding=mobile/android/branding/nightly", "ac_add_options --with-branding=mobile/android/branding/aurora")

        if abf == "l10n-nightly":
           file_replace(mozilla_aurora+abd+abf, "ac_add_options --with-l10n-base=../../l10n-central", "ac_add_options --with-l10n-base=..")

print("diff for branding changes..")
call('hg diff -R'+mozilla_aurora, shell=True)

raw_input("If the diff looks good hit 'return' to continue to commit..")
call('hg -R '+mozilla_aurora+' commit -m "Merging in branding changes NO BUG CLOSED TREE ba=release"',shell=True)
call('hg out -R'+ mozilla_aurora , shell=True)

raw_input("Hit enter to move on to Profile changes")

## disable profiling and elf-hack
aurora_profiling_files = ["mobile/android/config/mozconfigs/android/nightly", "browser/config/mozconfigs/linux32/nightly", "browser/config/mozconfigs/linux64/nightly", "browser/config/mozconfigs/macosx-universal/nightly", "browser/config/mozconfigs/win32/nightly", "browser/config/mozconfigs/win64/nightly"]

for apf in aurora_profiling_files:
    file_replace(mozilla_aurora+apf, "ac_add_options --enable-profiling\n", "")
    file_replace(mozilla_aurora+apf, "ac_add_options --disable-elf-hack # --enable-elf-hack conflicts with --enable-profiling\n", "")

print("diff for profile changes ...")
call('hg diff -R'+ mozilla_aurora , shell=True)

raw_input("If the diff looks good hit 'return' to continue to commit..")
call('hg -R '+mozilla_aurora +' commit -m "Merging in branding changes NO BUG CLOSED TREE ba=release"',shell=True)
call('hg out -R'+mozilla_aurora, shell=True)

## clear dtrace & instruments on mozconfigs higher than nightly see bug 748669
aurora_dtrace_files = ["browser/config/mozconfigs/macosx-universal/nightly"]

for apf in aurora_dtrace_files:
    file_replace(mozilla_aurora+apf, "ac_add_options --enable-instruments\nac_add_options --enable-dtrace\n", "")

raw_input("Verify the diff for dtrace changes ...")
call('hg diff -R'+mozilla_aurora, shell=True)

raw_input("If the diff looks good hit 'return' to continue to commit..")
call('hg -R '+ mozilla_aurora +' commit -m "Remove dtrace & instruments in mozconfigs on Aurora as per bug 748669 CLOSED TREE ba=release"' , shell=True)
call('hg out -R'+ mozilla_aurora , shell=True)

raw_input("Return to the wiki to do the L10n data changes ..")


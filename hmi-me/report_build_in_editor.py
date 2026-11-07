from __future__ import print_function
import os
base=r'C:\Users\sajic\Documents\plc-hackathon\hmi-me'
assert projects.primary.path.lower().endswith('me_v7_webvisu.project')
errors=[];warnings=[]
with open(os.path.join(base,'dashboard_messages.log'),'w') as f:
    for cat in system.get_message_categories(True):
        title=system.get_message_category_description(cat)
        f.write('CATEGORY %s %s\n' % (cat,title))
        for msg in system.get_message_objects(cat):
            f.write('%s %s\n' % (msg.severity,msg.text))
            if title in ('Build','Additional code checks'):
                if str(msg.severity) in ('Error','FatalError'):errors.append(str(msg.text))
                elif str(msg.severity)=='Warning':warnings.append(str(msg.text))
with open(os.path.join(base,'dashboard_build.log'),'w') as f:
    f.write('DASHBOARD_BUILD_RESULT errors=%d warnings=%d\n' % (len(errors),len(warnings)))
    for msg in errors:f.write('ERROR '+msg+'\n')
    for msg in warnings:f.write('WARNING '+msg+'\n')
print('DASHBOARD_MESSAGES_REPORTED')

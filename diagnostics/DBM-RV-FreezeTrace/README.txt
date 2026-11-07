DBM-RV FreezeTrace 0.3.4 TEST / FTRACE-20261107-01

Diagnostic companion for Aggramar and Argus, Interface 70300.
The canonical journal is DBMRVFreezeTraceDB in SavedVariables. The collector
archives this file after a normal logout. /reload writes a checkpoint to disk.
SavedVariables binding is restored at ADDON_LOADED and PLAYER_LOGIN.

Normal operation is quiet: no diagnostic whispers. The update migrates the old
key/full default to disk off once; enabled state and existing history survive.
Later explicit /rvtrace disk key or full persists across reloads. Optional chat
breadcrumbs are limited to one message per 2 seconds and 20 per target encounter.
Key mode transports only encounter boundaries and explicit markers. These limits
affect chat transport only; the existing bounded in-memory journal still records
events. No automatic chat history hiding or filter is installed.

/rvtrace status | summary | on | off | session ID | mark TEXT | disk off|key|full
Do not clear before archiving. This companion does not change boss warnings,
legitimate raid announcements, SavedVariables names or DBM-Core.

STATIC_VERIFIED is not a game test of the new version.

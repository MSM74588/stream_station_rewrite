- [x] player.py Router -> implement mpris player

- UPTO before /player/pause

- [ ] Replace all PRINT statements with proper Logging

- [ ] get repeat status from MPD player dynamically, and also set it to toggle, now its just on.

- [ ] Make a new, filesystem MPD player, that inits a new config file if a file_path is passed, then plays that file, and if a dir is passed it will play all the songs one by one, needed for CD Playback or pendrive playback
- [ ] It shoukd also accept a type parameter, so if its a dir type it will add them to mpd, and if its a file, it will only add that file and play that file, this is important for SECURITY.
- [ ] The filesystemMPDPlayer should have a different MPD_PORT. and should have a different directory, since the dir will be emptied quite often. For this the Queue should be off. 

- [ ] History Logging into database
- [ ] Queue listener. (for MPV : special cases for MPD CD cases or MPD DirPlayer CASES)

- [ ] Unexpected behavior of spotify sync when fetching into a fresh empty DB

# NOTE:
- Dependency Injection and Custom Context Manager for players (~ Session Manager).

# KNOWN BUGS:
- The songs must be more than 15 sec long at minimum or it can mess up the queue system since allocation of the song name takes time since it is being fetched by ytdlp inside MPV player(specific to youtube player)
- If network is slow, this can get furthur messed up, FIX THIS. 
- Points of Failure: (Needs Improvement, or redo)
        - wait_until_finished() in app/utils/player_utils.py
        - play_next_in_queue() in app/utils/media_handlers.py
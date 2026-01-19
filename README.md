# Smart RSVP

Smart RSVP is a Python-based speed reading tool built with tkinter. It utilizes the Rapid Serial Visual Presentation (RSVP) method to display text one word at a time at a fixed focal point, allowing you to read faster by eliminating saccadic eye movements.

This specific implementation is optimized for scientific papers in PDF format. It includes a parsing algorithm to strip out metadata, citations, and non-prose elements, to ensure a seamless reading flow.

## Features

- RSVP Display: Centers words arround a pivot character in red to allow focal reading.
- WPM Control: Adjustable Words Per Minute (default: 350).
- Text Visualizer: Allows the user to see the original uploaded text, and highlights in red the parsed out sections.
- Dictionary Warning: In order to properly sanitize the document, the user needs to download the [Webster's English Dictionary](https://github.com/matthewreagan/WebstersEnglishDictionary/blob/master/dictionary.json) and save it as `dictionary.json` in the project's folder.

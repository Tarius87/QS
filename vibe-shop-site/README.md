# Vibe Shop Class site redesign ("Circuit")

A one-page version of vibeshopclass.com. It replaces the long scrolling page with five tabs that switch in place:
Start, Vibe coding, Lessons, How it works and Get the lessons.

- **Shape:** the 45° cut corner from the circuit traces in the logo art.
- **Motion:**
  - Each tab has a circuit board whose traces draw themselves, with signals running along them.
  - A trace connects the tab you pick to the section it opens.
  - Highlighted words decode like data.
  - The lesson-plan steps tick off as a signal reaches them.
- **Colors on every tab:** about 60% white or cream, 30% teal and 10–15% peach.

Unchanged from the live site:
- Brand colors and fonts, and all the copy.
- YouTube embeds, with lessons and Shorts that switch on by release date.
- The Supabase email signup and `unsubscribe.html`.
- GoatCounter analytics and `CNAME`.
- Visitors who turn off animations get a calm version.

Links: `#start`, `#vibe`, `#lessons`, `#lessons-3`, `#how` and `#join`. The old site's `#lesson-N`, `#signup` and `#lesson-bar` links still work.

## Going live

This folder holds the files only. The live site comes from the `Tarius87/VibeShopClass-site` repo:

1. Copy everything in this folder into the root of that repo.
2. Keep that repo's `.github/workflows/keep-supabase-awake.yml` and `.nojekyll`.
3. `chart.js`, `datalabels.js`, `hark*.js`, `hark*.css` and `vsc-lockup.png` are no longer used and can be deleted there.

To publish a video, paste its YouTube ID into `VIDEOS` / `SHORTS` at the top of the script in `index.html`.

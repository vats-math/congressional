# Forsyth County, GA data: sources and verification log

Every row in programs.csv was read from the source page below on **2026-10-19**.
"Verified" here means *the fact is stated on that page*. It does NOT mean someone called the program.
Anything not stated on the page is left blank or marked `unknown`, never guessed.

## What each source gave us

| Programs (ids) | Source page | Facts taken from it |
|---|---|---|
| `ufa-rec-*` (20 rows) | https://www.unitedfa.org/forsyth-rec-seasonal-info (Rec Fall 2026 Season Info) | Practice day and time for every girls/coed division at Central Park, Polo Fields, Matt Community Park and South Forsyth Soccer Complex; no skill-level requirement; assessments for U5-U12 "not a tryout", U14/U16/U19 not assessed; fall calendar (registration to Jul 15, $25 late fee from Jul 16, practices from Aug 31, games Sep 12 - Nov 14, fall break Sep 27 - Oct 4); volunteer parent coach per team |
| `ufa-rec-*` ages | https://www.unitedfa.org/recreational-new-age-group and https://www.georgiasoccer.org/wp-content/uploads/sites/175/2026/02/2026_2027-Age-Group-Chart_020526_academicyr.pdf | 2026-27 groups run Aug 1 - Jul 31. **Ages in the CSV (U10 = 9-10, U12 = 11-12, U14 = 13-14, U16 = 15-16, U19 = 17-18) are DERIVED**, not printed on one page. Confirm on UFA's age-group calculator |
| `crpd-winter-bball-girls-*` (4 rows) | https://www.active.com/cumming-ga/basketball/basketball-classes/rec-winter-basketball-league-2026 | Girls divisions 9&10, 11&12, 13&14, 15&16; online registration ended Oct 9, 2026; refund deadline Oct 23; evaluations are not tryouts and everyone is placed on a team; practices early Nov, once a week; games from Sat Dec 5, 2026; address and phone 770-781-2030 |
| `fcpr-winter-bball-girls-10u-12u` | https://secure.rec1.com/GA/forsyth-county-ga/leagues | The county's league system lists 10U Girls and 12U Girls winter basketball. Dates/fee for 2026-27 not found |
| `gotr-georgia-forsyth` | https://www.atlantanewsfirst.com/2026/07/29/girls-run-georgia-empowers-girls-one-step-time/ and https://www.gagives.org/organization/girlsontherunga | Girls grades 3-8; 12-week season, teams meet twice a week; sliding scale from $0; Forsyth is a served county |
| `nfms-intramurals` | https://nfms.forsyth.k12.ga.us/extracurricular/athletics/nfms-intramurals-information | Grades 6-8; 7:30-8:25 AM in the gym; days announced by PE teachers; no physical required; permission slip required |
| `nfms-girls-basketball`, `nfms-track-field` | https://nfms.forsyth.k12.ga.us/extracurricular/athletics/coaches-eligibility-physicals-and-intramurals | Grades 7-8; eligibility (passed 5 of 6/7 classes, physical on DragonFly, proof of insurance); 7th/8th girls basketball and track & field exist; address 3645 Coal Mountain Drive, Cumming 30028 |
| `fcs-high-school-athletics` | https://www.forsyth.k12.ga.us/district-services/community-engagement-lifelong-education/school-activities-and-athletics | All county high schools are GHSA members |
| `happy-feet-tennis-sharon-springs` | https://hftacademy.com/ | Ages 5-18, Mon-Thu classes, summer 2026 prices ($20/$30/$40 per class), not accepting new players this school year (Sharon Springs Park renovation), summer ended Jul 31 |
| `*-tennis-courts` | https://exploregeorgia.org/sports-professionals/host/forsyth-county | Fowler Park has 12 tennis courts, Central Park has 8 |
| Addresses | Fowler Park 4110 Carolene Way and Central Park 2300 Keith Bridge Rd come from the county's own press releases | |

## Known limits (say these out loud in your submission)

1. **Nobody has called these programs.** Do the call list below before you demo.
2. **UFA times are the Fall 2026 schedule.** UFA states days/times can change before a season; spring will differ.
3. **No program has a verified 2026-27 price** except Girls on the Run (sliding scale from $0). Costs are blank and shown as "See website".
4. **Status** is `closed`/`upcoming`/`unknown`, because several programs are in season or past registration today. The app must not tell a student to "sign up Tuesday" for a closed program.
5. Ages derived from grades (middle school, GOTR, high school) and from U-groups are marked as derived in each row's description.

## Not in the database yet (found, but not verifiable from a source I could open)

Forsyth County Parks & Recreation blocked automated access to its own pages, so these are on the **call list** instead:

- Forsyth County Parks & Rec: youth softball (fall instructional + spring), camps and clinics, 2026-27 winter basketball fee/dates, 14U girls basketball. Phone numbers seen in county materials: Parks & Rec 770-781-2215; Central Park rec center 678-455-8540; Fowler Park rec center 770-886-4088; Old Atlanta Park rec center 770-205-4646.
- Forsyth County high school teams per school (tryout dates), and the other ten middle schools' athletics/intramurals.
- Girls on the Run Georgia: which Forsyth schools host teams in the next season, days and times.
- Volleyball, lacrosse, swimming, flag football, Boys & Girls Clubs of Lanier (Forsyth location), Special Olympics, TOPSoccer (UFA lists it), UFA Fast Track/clinics.
- Tennis: James Creek Tennis Center, Creekstone Tennis Academy (both appear in tennis directories; no current junior schedule found).

## Call script (2 minutes per program)

"Hi, I'm building a free app that helps girls in Forsyth County find sports. Can I confirm three things for your [program]? 1) What days and times does it meet? 2) What does it cost and is there financial aid? 3) When is the next sign-up, and does a beginner need any experience or a tryout?"
Write the answer, the date and who you spoke to in a new column and update `last_verified`.

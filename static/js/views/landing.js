// Landing page. The copy here is the team's to rewrite (see README "Copy").
import { $ } from "../dom.js";
import { blankProfile, state } from "../state.js";
import { scoreColor } from "../ui.js";

export function html() {
  return `
  <section class="hero">
    <div>
      <p class="kicker">For girls and women in sport</p>
      <h1>Find where you <em>play</em> next.</h1>
      <p class="lede">PlayPath matches you with real teams, leagues, camps, and programs from schools, colleges,
        rec centers, nonprofits, and clubs, ranked by how well they fit you.</p>
      <div class="cta">
        <a class="btn" href="#/signup">Find my opportunities</a>
        <a class="btn ghost" href="#/explore">Explore the map</a>
      </div>
      <a class="textlink" href="#/quiz" data-guest="1">or continue as a guest →</a>
    </div>
    <div class="hero-art" aria-hidden="true">
      <div class="hero-card"><span class="score" style="background:${scoreColor(94)}">94</span><div><b>Dallas Cup Girls Divisions</b><small>Tournament · 9 mi · travel</small></div></div>
      <div class="hero-card"><span class="score" style="background:${scoreColor(82)}">82</span><div><b>YMCA Youth Soccer (Girls)</b><small>Recreation · local chapter</small></div></div>
      <div class="hero-card"><span class="score" style="background:${scoreColor(57)}">57</span><div><b>College ID Camp</b><small>College · 450 mi</small></div></div>
      <p class="hero-note">Example scores. Yours depend on your answers.</p>
    </div>
  </section>

  <section class="why-section">
    <div>
      <h2>Why we built this</h2>
      <p>By age 14, girls drop out of sports at about twice the rate of boys. One reason is simply not knowing what's
        out there, what it costs, or whether they're eligible. The options are scattered across hundreds of club
        sites, school pages, and rec department flyers.</p>
      <p>We wanted one place that gathers them, explains them honestly, and points each athlete to her next step.</p>
    </div>
    <ul class="facts">
      <li><b>Real listings</b><span>Every result is a program in our database with a link to its official site. Nothing is generated.</span></li>
      <li><b>Worldwide map</b><span>See where programs are, how clustered they are, and what's affordable.</span></li>
      <li><b>Honest about gaps</b><span>Our data is strongest for U.S. soccer right now, and we say so.</span></li>
    </ul>
  </section>

  <section class="how">
    <h2>How it works</h2>
    <ol class="steps">
      <li><span>1</span><b>Take the quiz</b><p>Sport, age, level, schedule, budget, how you get around, and anything that makes it harder to play.</p></li>
      <li><span>2</span><b>We score every program</b><p>A ranking algorithm weighs 9 factors, including sport, age, skill, distance, cost, travel, and deadlines, and checks eligibility.</p></li>
      <li><span>3</span><b>Get your plan</b><p>A weekly plan built around your free time, a suggested next level, and a pathway toward your goal.</p></li>
      <li><span>4</span><b>Explore and adjust</b><p>Browse the map, open any program to see why it matches, and change your answers anytime.</p></li>
    </ol>
  </section>`;
}

export function after() {
  $("[data-guest]")?.addEventListener("click", () => { if (!state.profile) state.profile = blankProfile(); });
}

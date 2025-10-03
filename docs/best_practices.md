# Adventure Design Best Practices

This guide distils lessons from the scripted demo, analytics utilities, and
multi-agent experiments into a set of practical tips for authors building new
adventures with the `textadventure` framework. Treat the checklist as a starting
point and adapt it to the tone and complexity of your own stories.

## Plan the Structure First

- **Map your scenes and progression.** Sketch the major locations, the choices
they expose, and the transitions that connect them before opening your editor.
  The [`compute_scene_reachability`](../src/textadventure/analytics.py) helpers
  can then confirm every intended location is actually reachable once the JSON
  is written.
- **Decide on win/lose states early.** Identifying terminal transitions up
  front keeps the pacing tight and avoids players wandering without closure.
- **Reserve room for optional side paths.** Keeping a few scenes off the golden
  path makes it easier to demonstrate the analytics reports that flag
  unreachable content or orphaned items.

## Craft Clear Choices

- **Keep commands short and memorable.** The CLI compares commands
  case-insensitively, so prefer one or two words that are easy to type. Avoid
  overlapping verbs between different scenes unless they do the same thing.
- **Describe intent, not implementation.** Choice descriptions should hint at
  outcomes without spoiling surprises. This aligns with how `StoryEvent`
  entries are formatted in the CLI transcript log.
- **Group related actions.** When a scene offers many micro-actions, consider
  breaking them into multiple scenes connected by simple navigation choices.
  This keeps the `format_event` output readable and reduces analysis noise.

## Use Inventory and History Thoughtfully

- **Grant items sparingly.** Each transition can award at most one item via the
  `item` field. Use the analytics `analyse_item_flow` report to ensure items are
  both awarded and consumed somewhere in the adventure.
- **Prefer `requires` over narrative reminders.** Let the engine block actions
  until prerequisites are satisfied instead of relying on the player to read a
  hint. Provide a `failure_narration` when the default reminder is too vague.
- **Record meaningful history.** The `records` field appends journal entries via
  `WorldState.remember_observation`. Use them to unlock conditional narration
  (`narration_overrides`) or to drive later scene branches.

## Layer Conditional Narration

- **Start with a default narration.** Every transition and conditional override
  should include a sensible baseline so unexpected world states do not leave the
  player without feedback.
- **Combine history and inventory filters.** Overrides can check inventory and
  history simultaneously, enabling richer callbacks when the player returns to a
  scene. Keep filter lists short and descriptive to simplify debugging.
- **Log additional records in overrides.** Because overrides run after the base
  transition succeeds, they are a great place to note flavourful achievements or
  to track optional steps for later recaps.

## Embrace Tools and Secondary Agents

- **Surface optional knowledge through tools.** Map commands such as `guide`
  (used by `KnowledgeBaseTool`) to lore lookups instead of bloating scene
  descriptions.
- **Use multi-agent narration for contrast.** The `MultiAgentCoordinator` can
  pair the scripted narrator with an `LLMStoryAgent`. Give each agent a clear
  role—one might deliver exposition while the other reacts emotionally.
- **Document tool and agent expectations.** If a scene relies on a tool or
  secondary agent to progress, record that in the adventure notes so playtesters
  know how to reproduce the experience.

## Test and Iterate Continuously

- **Run the CLI with transcripts enabled.** Launch `python src/main.py --log-file
  transcripts/session.log` to capture narration, choices, and metadata in a
  timestamped log for later review.
- **Exercise the `status` command often.** It prints the current location,
  inventory contents, queued agent messages, and pending saves—handy when
  debugging gated transitions or multi-agent timing issues.
- **Automate regression coverage.** Mirror new mechanics with unit tests in the
  `tests/` directory so future refactors do not break authored adventures.

## Leverage Analytics Before Shipping

- **Complexity report.** Use
  `textadventure.format_complexity_report(compute_adventure_complexity(...))` to
  understand overall breadth, interactive density, and gating hot spots.
- **Content distribution report.** Call
  `format_content_distribution_report` to catch missing descriptions or unusual
  text length extremes.
- **Quality report.** The analytics module highlights transitions missing
  narrations, gated paths without failure responses, and other quality red
  flags—treat it as a pre-flight checklist.
- **Item flow report.** Before release, ensure every item is awarded and used in
  at least one location so players never carry dead weight.

## Share Your Learnings

- **Document bespoke rules.** Adventures that introduce custom mechanics,
  unusual commands, or optional agents should ship with a README or design note
  so collaborators can ramp up quickly.
- **Update the backlog.** As you discover recurring pain points or new feature
  ideas, record them in `TASKS.md` so future contributors can continue to level
  up the tooling.

By following these guidelines you will keep adventures approachable for players,
maintainable for developers, and ready for richer agent-driven storytelling.

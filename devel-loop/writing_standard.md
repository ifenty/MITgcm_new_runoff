# Writing standard for text that people read

All text that a person reads follows ASD-STE100 (Simplified Technical English).
This rule applies to every role, including Arch, Bob and Richard.
It applies to new text and to text that you change.
Long and confusing text costs the owner time. Short and clear text saves it.

## Credit

The structural rules, the word rules, the scan checklist and the linter `tools/esx/ste_lint.py` come from the
skill [asd-ste100](https://github.com/danyuchn/asd-ste100-skill) by Dustin Yuchen Teng. The skill has the MIT license.
The kit file `THIRD_PARTY_NOTICES.md` has the license text.
The ASD-STE100 specification belongs to ASD, the AeroSpace and Defence Industries Association of Europe.

## What the rule covers

The rule covers the text in these places:

- Open issues, closed issues, and the notes on a scope decision.
- Lessons learned and their evidence notes.
- Long-term goals and milestones.
- Current status, closeout summaries and retrospective commentary.
- Messages and heartbeats that Arch sends to the owner. Also every answer or report to the owner.
- Every document of the project, including the project profile, the model contract and the code map.
- The `summary`, `limits` and `reason` fields of a footer or a closeout. These fields become record text.

The rule does not cover these items:

- Source code, comments in the code, and the output of a tool.
- Names of files, commands, options and fields. Write them exactly, in code font.
- A brief to a role, if no person reads it. Use the rule where it is easy.
- Closed history. Do not rewrite a closed record only to change its style. Rewrite it when the owner asks.

## Choose a mode

| Mode | Use it for | Rules |
|---|---|---|
| Strict | Procedures, error messages, instructions to a role, text that blocks work | All rules below, including one word for one meaning. |
| STE-flavored | Issues, lessons, goals, status, README files, changelogs, explanations | All structural rules. The word rules are advice. |

Strict text must be flat and literal. Prose needs some range of words.
A strict rewrite of a long explanation can lose its meaning.

## Structural rules

Apply these rules in full.

| Rule | Do | Do not |
|---|---|---|
| Active voice | "The agent writes the file." | "The file is written." |
| Phrasal verbs | "Remove the panel." "Start the job." | `Take off the panel.` `Spin up the job.` |
| One instruction in each sentence | "Open the file. Read line 3." | "Open the file and read line 3, then check it." |
| Sentence length | 20 words or fewer in a procedure. 25 words or fewer in a description. | A long sentence with several clauses. |
| Semicolons | Split the sentence in two. | Any semicolon. |
| Noun groups | 3 nouns or fewer in a row. | "high pressure fuel pump inlet valve assembly" |
| Ellipsis | Keep the subject, the verb and the article. | "Files not backed up are lost." |
| Hedges | Keep "may have failed" as it is. | Change a hedge into a fact. |
| Paragraphs | One topic. 6 sentences or fewer. | A paragraph with several topics. |
| Lists | Use a list for 3 steps or more. | Hide a sequence in one sentence. |

Also apply these rules:

- Use the articles "the", "a" and "an". Do not leave them out.
- Use "must" for a requirement and "can" for a possibility. Do not use "should".
- Do not use idioms or contractions.
- Put a warning before the step it applies to.
- Write numbers as digits. Put a space before the unit: "15 minutes", "4 GB".
- State what you measured, on which date, and with which command. Do not write a number that nobody measured.

## Word rules

Apply these rules as a direction. The official dictionary of approved words is not in this kit.

| Rule | Do | Do not |
|---|---|---|
| One word for one meaning | Use "check" each time. | Use `check`, `verify` and `confirm` for one action. |
| Verb, not noun | "Analyze the log." | `Perform an analysis of the log.` |
| One part of speech | "Apply oil to the valve." | "Oil the valve." |
| Technical terms | Keep the term. Define it one time. | Use a term that nobody defined. |

## Tenses

Use the simple present tense for facts. Use the simple past tense for events that finished.
Use the imperative for instructions. Do not use the present perfect: write "we received the report".

There is one exception. Sometimes the present perfect carries information that the simple past does not.
"The job has completed" tells that the output exists now. Keep that form and mark it.

## Scan checklist

Look for these six habits before you rewrite a text. You can point at the exact words for each habit.

1. **Synonym rotation.** The same thing has several names. Pick one name and use it each time.
2. **Hedge stacking.** Helper words pile up until the sentence says nothing. State the claim or remove it.
3. **Nominalization.** An action became a noun, as in `perform an analysis of`. Use the verb.
4. **Marketing adjectives.** Words such as `seamless`, `robust` and `powerful` claim quality. Remove them or give the measurement.
5. **Run-on sentences.** Several ideas share one sentence. Write one idea in each sentence.
6. **Soft phrasal verbs.** `Spin up`, `reach out` and `kick off` are unclear. Use "start", "contact" and "read".

## How to rewrite

1. Read the text one time for its meaning. Do not rewrite before you understand it.
2. Mark each sentence that breaks a rule or shows a habit from the checklist.
3. Rewrite each marked sentence. Keep every fact, number, condition and scope.
4. Keep the strength of every hedge. A hedge is content. "May have failed" is not "failed".
5. Do not add a fact that the source did not state.
6. If a short sentence loses a condition, keep the long sentence. Add one line after the text: "Kept as-is: ...", with the phrase and the reason.
7. Stop when the text has one meaning. Do not make the text as short as possible.
8. If the text is already clear, do not change it.

A rewrite fixes the form of a text. It does not fix the substance.
A text with nothing to say stays empty after a rewrite. Say so and ask the author for the facts.

## An issue entry in this style

Keep the fields of the record. Write the content of each field in short sentences.

| Field | Write |
|---|---|
| Issue | What is wrong or unknown, in 1 to 3 sentences. Give the file and the line. |
| Evidence | What you measured. Give the command, the date and the result. |
| Impact | What happens if nobody fixes it. Say who it affects. |
| Action and acceptance | What to do, and the check that shows the work finished. |

Do not write the history of an issue as one long paragraph.
Write each dated update as its own short paragraph. Start it with the date and the cause.

## A lesson in this style

Write the lesson as one rule in 1 or 2 sentences. Write the trigger as "Use this when ...".
Put the detail in the evidence note. Write that note in short sentences too.

## Check your text with the linter

The tool `tools/esx/ste_lint.py` checks the structural rules that a program can check.

```sh
python3 tools/esx/ste_lint.py FILE [FILE ...]
python3 tools/esx/ste_lint.py --baseline 5 FILE
python3 tools/esx/ste_lint.py --disable passive-voice FILE
```

- A hard violation makes the exit code 1. The hard rules are sentence length, semicolons, phrasal verbs,
  nominalization, marketing adjectives, synonym rotation and noun groups.
- A passive verb or a compound tense is advice only. The exit code stays 0.
- The linter never flags a hedge. A hedge is content.
- `--baseline N` accepts N hard violations. Use it on an old record that you cannot rewrite at once.
- The linter reads a quoted example as a normal sentence. Quote a rule violation on purpose in a code block.

The linter cannot check meaning. Read the text again after the linter passes.

## Limit of this rule

The ASD-STE100 specification has a dictionary of about 900 approved words. The dictionary is not in this kit.
ASD allows only listed groups to copy it. The rules above are the writing rules of the specification in short form.
Text that follows them is easier to read. It is not a formal STE validation.
For text that needs formal compliance, get the specification from `https://www.asd-ste100.org` and check each word.

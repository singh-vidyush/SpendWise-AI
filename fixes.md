FIX CHAT UI WITHOUT BREAKING PDF DOWNLOAD FEATURE

You are working on an existing SpendWise project.

The PDF download feature was recently added successfully, but it unintentionally broke the chat UI/UX.

Current Problem

The assistant response is now being rendered as a large raw markdown/text block directly in the chat area.

Symptoms:

Huge wall of text
Poor spacing
Markdown formatting not styled properly
Looks like a plain document pasted into chat
Download button appears, but overall chat experience feels broken
The previous UI was significantly cleaner

I have attached a screenshot showing the current issue.

What the Chat Looked Like Before

Before adding the download button:

User messages appeared in attractive chat bubbles.
Bot messages appeared in attractive assistant cards.
Proper spacing between messages.
Nice readability.
Professional chatbot appearance.
Consistent typography.
Chat felt conversational.

I want that exact experience back.

What I Want

Keep ALL current functionality:

✅ download button

✅ pdf generation

✅ conversational flow

✅ financial analysis flow

✅ chat history

✅ LangGraph workflow

✅ backend APIs

✅ agent outputs

But restore the visual quality of the chat.

Root Cause To Investigate

The implementation likely replaced the original custom message rendering system with direct Streamlit markdown rendering.

Examples of things that may have happened:

st.markdown(response_text)
st.write(response_text)
st.chat_message markdown without styling
rendering raw report text directly

The original project already had:

custom bot_message()
custom user_message()
custom CSS
custom assistant bubble styling

I want those preserved.

Frontend Requirements

Focus primarily on:

frontend_app.py

Do not redesign the application.

Do not convert the app into a completely different chat UI.

Restore the existing design system.

Assistant Messages

Assistant messages must continue using the existing custom assistant component.

Example:

SpendWise AI

Financial Analysis...

Recommendations...

Market Insights...

The response should appear inside the same styled assistant card used before the PDF feature was added.

User Messages

User messages must continue using:

original styling
original speech bubble design
original colors
original spacing

Do not modify user bubbles.

Download Button Placement

The button must appear BELOW the assistant message.

Structure should be visually:

Assistant Card

Response Text

Recommendations

Market Insights

[📄 Download Financial Report]

Not:

Response Button Response Button

Not:

Button floating elsewhere

Not:

Button outside chat container

Conversational Flow Requirements

If intent = conversational

Show:

Assistant Card with generated response

No PDF button

No placeholder

No empty space

No visual artifact

Financial Analysis Requirements

If intent = financial_analysis

Show:

Assistant Card with generated response

Then directly below it:

Download PDF Button

Only for that message.

Message Rendering Requirements

Do NOT render financial reports as giant markdown documents.

Instead:

maintain existing chat appearance
preserve line breaks
preserve readability
preserve headings
preserve bold formatting

Convert long reports into attractive chat content.

Markdown Handling

Current reports contain:

headings
bullets
numbered sections
bold text

Ensure markdown is rendered correctly inside the assistant message card.

Examples:

Executive Summary

should visually appear as a section heading.

Bullets should remain bullets.

Bold text should remain bold.

Do NOT display raw markdown characters.

Chat Layout Requirements

Maintain:

padding
margins
border radius
shadows
spacing
assistant avatar
user avatar

Use the styling system already present in the project.

Do not introduce a completely new design language.

Common Mistakes To Avoid

Do NOT:

replace bot_message() with st.write()
replace custom cards with plain markdown
duplicate the response
display pdf path
display debug information
show raw JSON
show raw markdown text
create a second chat container
Investigate Existing Functions

Before making changes:

Inspect:

bot_message()
user_message()
advisor_chat()
submit_advisor_question()
advisor_response()

Understand how messages were originally rendered.

Reuse that architecture.

Expected Final UX

Conversation example:

User: Analyze my finances

Assistant: ────────────────── 🤖 SpendWise AI

Executive Summary

Your current savings rate...

Recommendations

Increase SIP
Build emergency fund

Market Insights

Inflation remains...

──────────────────

📄 Download Financial Report

User: What is inflation?

Assistant: ────────────────── 🤖 SpendWise AI

Inflation refers to...

──────────────────

(no button)

Success Criteria

After implementation:

✅ Chat looks exactly like original beautiful UI

✅ Assistant responses display inside styled chat cards

✅ User messages unchanged

✅ Download button appears only for financial-analysis responses

✅ Conversational responses show no button

✅ No raw markdown wall of text

✅ No duplicated messages

✅ No loss of existing functionality

✅ No backend architectural changes unless strictly necessary

Priority:

Restore old beautiful chat UI
Keep PDF download functionality
Keep all existing business logic unchanged
Modify frontend rendering only whenever possible
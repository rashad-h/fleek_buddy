I want to create a end-to-end product for a that simulates a chat between a buyer and a seller. The product should be able to list items, provide item details, and allow the buyer to haggle with the seller. The seller account operates as a deal negotiator agents that haggles and closes wholesale bundles.

We need to restructure the codebase to support a UI. You can refer to @../../../templates/tanstack-start-template/ and use the tanstack for UI only. Also get the claude skills over before starting to plan.

- Use fleek colours and styles for the UI -> https://www.joinfleek.com/home
- - The platform represents the buyer point of view while the seller is represented by the agent operated by the backend
- The items are listed programmatically before running the app using seeding (currently available, needs tweaking), so the should be already available on the platform when I demo it. No listing. Items needs to have data based on this listing: https://www.joinfleek.com/products/under-armour-sexy-shorts?click_source=COLLECTIONS&click_source_details=Most+Wanted . On top of this data, the item should have some "haggle" metadata. A flag that indicates whether there is a high quantity of the item available, a flag that indicates whether the item is negotiable, buying price, lowest price, as a bundle, lowest price per piece.
- As a buyer, I can select an item from the dashboard
- The item should have a "make an offer" button similar to fleek (no other buttons)
- As the buyer, I will click the "make an offer" button and a modal should pop up with a form to enter my offer price. The form should have a submit button to send the offer to the seller agent
- When an offer for the item is sent, I need a separate chat window to open up for the buyer and seller to negotiate. The chat window should have a message input box and a send button. The chat should be real-time, so when the buyer sends a message, it should appear in the chat window for the seller agent to see and vice versa.
- The seller agent should receive the offer and respond with a counteroffer or accept/reject the offer based on context. The response should be sent back to the buyer in real-time.
- The chat should have a history of messages exchanged between the buyer and seller agent
- the buyer should be able to send messages and the agents should respond
- If the agent agrees to the offer, the chat should display a message indicating that the offer has been accepted and the transaction is complete. If the agent rejects the offer, the chat should display a message indicating that the offer has been rejected and the buyer can make another offer or end the negotiation.

I need guidance on hoe to set up the agent as I am not sure how to set up the agent to respond to the buyer's offers. I want the agent to be able to negotiate and close deals based on the haggle metadata of the items and the context I provide to it. This context should be easy to enrich with other sources in the code. The agent should be able to evaluate the buyer's offer and respond with a counteroffer or accept/reject the offer based on the item's haggle metadata and other context provided. The agent should also be able to handle multiple buyers and items simultaneously, and maintain a history of negotiations for each item.

Also update the @README.md to reflect how to run the app and steps to take before the demo thoroughly.

Ask questions if you have doubts about the requirements or if you need clarification on any aspect of the product.
When you have enough information to act, act. Do not re-derive facts already established in the conversation, re-litigate a decision the user has already made, or narrate options you will not pursue in user-facing messages. If you are weighing a choice, give a recommendation, not an exhaustive survey. This does not apply to thinking blocks.

Provide concise, focused responses. Skip non-essential context, and keep examples minimal.

Delegate independent subtasks to subagents and keep working while they run. Intervene if a subagent goes off track or is missing relevant context.

Store one lesson per file with a one-line summary at the top. Record corrections and confirmed approaches alike, including why they mattered. Don't save what the repo or chat history already records; update an existing note rather than creating a duplicate; delete notes that turn out to be wrong.

If you need to clarify anything, ask rather than assuming.

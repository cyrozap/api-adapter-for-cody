# LLM API Adapter for Sourcegraph Cody

This is a Python Flask application that presents a (partly) OpenAI-compatible API through which you can make queries to Sourcegraph's (undocumented) API for their [Cody LLM service][cody].
The Cody API appears to itself be a thin adapter over the LLM APIs that Cody has access to (Anthropic, Fireworks, Google, Mistral, and OpenAI), so I suppose this project is an adapter for an adapter.
If you have a free Cody account, by using this adapter-for-an-adapter you can effectively get (rate-limited!) access to (some of those) APIs for free.
If you have a paid Cody account, you can access all of them, and supposedly the rate limits are significantly higher.

This is some of the worst code I have ever written.
I strongly suggest you not use it.

Honestly, this is more like art (or perhaps a shitpost?) than anything practical.
This is the kind of stuff I would write for myself for fun when I was in college, without any care for whether it would continue to work in three months or if the quality of the code was any good.
The purpose of those projects was purely to do something clever and fun that would serve a nominally functional purpose, might teach me something, and that I could show to my friends.

I had a lot of fun getting this working, and I was impressed at how well [Qwen2.5-Coder 32B][qwen] running locally at `q4_K_M` quantization was able to take the cURL commands and API responses I copy and pasted from the Chrome dev tools and generate working Python code (though not _good_ code).
This saved me maybe 30-60 minutes of copy/pasting and checking the documentation for Flask and Requests, and that was enough to take this project from, "Meh, too tedious to bother," to, "Sure, sounds like fun!"

As I greatly prefer to use local LLMs, I'm probably not going to work on this much further.
The license is [BSD Zero Clause License][0bsd], so you're free to do whatever you want with this code without crediting me.
In fact, I think I might _prefer_ not to be credited (haha), but I'll leave it up to you.


## Usage

> [!CAUTION]
> Use this code at your own peril! There's a good chance you'll quickly trip your rate limit (200 chat prompts per month for free accounts at the time of this writing), so if you start getting HTTP 429 errors that's what happened. Also, it should be pretty easy for Sourcegraph to detect your use of this program, and if they don't like you using it they can ban your account. I can't be held responsible if any of that happens to you!

1. Install dependencies: `pip install -r requirements.txt` (you'll probably want to do this inside a virtualenv)
2. If you're using a private Sourcegraph instance (e.g., https://customer.sourcegraph.com/, https://customer.sourcegraphcloud.com/, or a custom domain), set the `SOURCEGRAPH_DOMAIN` environment variable to the domain name of your instance.
   - If you're using the public Sourcegraph instance (https://sourcegraph.com/), you can leave this variable unset.
3. Start the server:
   - Development: `./llm_adapter.py`
   - "Production": `./start.sh` (to run on `localhost:5000`) or `./start.sh HOST:PORT` (to run on `HOST:PORT`)
4. Log in to the Cody web application on your Sourcegraph instance, then either generate an API token (the token starts with `sgp_`) or use your browser's dev tools (or an extension) to grab the value of the `sgs` session cookie.
5. In whatever program or library you're using to access the API:
   - Set the OpenAI API base url to the host and port the adapter is running on.
   - Set the OpenAI API key to the value of the `sgp_` API token or `sgs` session cookie you obtained earlier.
6. Have fun!


## To do (or not to do)

- [x] Authorize using Sourcegraph access tokens instead of grabbing the cookie from the browser (apparently the Cody CLI tool and editor extensions auth to the Cody API using access tokens).
- [ ] Add more complete support for the OpenAI-compatible API.
- [ ] Add better error handling in the stream endpoint (can we send along the status codes from the Cody API to the client?).
- [ ] Generally make the code not terrible.


[cody]: https://sourcegraph.com/cody
[qwen]: https://github.com/QwenLM/Qwen2.5-Coder
[0bsd]: https://spdx.org/licenses/0BSD.html

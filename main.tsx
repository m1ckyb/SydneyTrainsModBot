import { Devvit } from '@devvit/public-api';
import { appSettings } from './settings.js';

Devvit.configure({
  redditAPI: true,
  kvStore: true, // Enable Key-Value storage for tracking posts
  settings: appSettings,
});

// Configuration: AutoMod Rules
const RULES = [
  {
    name: "Disguised Links",
    // JS Regex for disguised links: captures text in group 'text' and ensures url doesn't match
    regex: /(\[(?<text>(?:http|www)\S+)\]\((?!\k<text>)(?:http|www)\S+\))/i,
    check: ['body'],
    action: 'remove',
    message: "The above submission by u/{{author}} was removed because it contained a disguised link."
  },
  {
    name: "URL Shorteners",
    domains: ['bit.ly', 'goo.gl', 'tinyurl.com', 'ow.ly', 'is.gd', 'buff.ly', 't.co'],
    check: ['domain'],
    action: 'remove',
    message: "Your submission was removed because you used a URL shortener ({{match}})."
  },
  {
    name: "Mobile Links",
    domainsStartsWith: ['m.', 'mobile.'],
    check: ['domain'],
    action: 'remove',
    message: "Your submission was automatically removed because you linked to the mobile version of a website."
  },
  {
    name: "Banned Domains",
    domains: ['twitter.com', 'x.com', 'team3thirty.com', 'd33doz.com.au', 'tripappy.co'],
    check: ['domain', 'body', 'title'],
    action: 'remove',
    message: "Your submission was removed because we don't allow links to {{match}}."
  },
  {
    name: "Spam Filter",
    regexes: [
      /qt-shirt\.com/i,
      /my-teespring\.com/i,
      /buy (it )?here\W*->/i,
      /grab yours here/i,
      /(crypto|bit)coin/i
    ],
    check: ['title', 'body'],
    action: 'spam',
    reason: "Potential Merchandise or Crypto Spam"
  },
  {
    name: "Profanity Filter",
    regexes: [
       /((bul+|dip|horse|jack).?)?sh(\?\*|[ai]|(?!(eets?|iites?)\b)[ei]{2,})(\?\*|t)e?(bag|dick|head|load|lord|post|stain|ter|ting|ty)?s?/i,
       /((dumb|jack|smart|wise).?)?a(rse|ss)(.?(clown|fuck|hat|hole|munch|sex|tard|tastic|wipe))?(e?s)?/i,
       /(cock|dick|penis|prick)\W?(bag|head|hole|ish|less|suck|wad|weed|wheel)\w*/i,
       /(m[oua]th(a|er).?)?f(?!uch|uku)(\?\*|u|oo)+(\?\*|[ckq])+\w*/i,
       /[ck]um(?!.laude)(.?shot)?(m?ing|s)?/i,
       /c+u+n+t+([sy]|ing)?/i
    ],
    check: ['title', 'body'],
    action: 'filter',
    message: "Profanity Filter Triggered"
  }
];

// Trigger: Runs every time a new post is created
Devvit.addTrigger({
  event: 'PostCreate',
  onEvent: async (event, context) => {
    const { reddit, kvStore, settings } = context;
    
    if (!event.post || !event.author) return;

    const author = event.author;
    const post = event.post;
    const title = post.title || '';
    const body = post.selftext || '';
    let domain = '';
    try {
        if (post.url && post.url.startsWith('http')) {
            domain = new URL(post.url).hostname.replace(/^www\./, '');
        }
    } catch (e) {
        console.log('Error parsing URL', e);
    }

    // 1. Check if author is a moderator (skip limits)
    const subreddit = await reddit.getCurrentSubreddit();
    const mods = await subreddit.getModerators();
    const isMod = mods.some(m => m.username === author.name);
    
    if (isMod) {
      console.log(`Skipping checks for mod: ${author.name}`);
      return;
    }

    // 2. Content Rules
    for (const rule of RULES) {
        let matched = false;
        let matchVal = '';

        const contentMap: Record<string, string> = { title, body, domain };
        const checks = rule.check || [];
        
        // Check regex
        if (rule.regex) {
            for (const field of checks) {
                const text = contentMap[field];
                if (text && rule.regex.test(text)) {
                    matched = true;
                    matchVal = text.match(rule.regex)?.[0] || '';
                    break;
                }
            }
        }
        // Check regexes list
        if (rule.regexes) {
            for (const regex of rule.regexes) {
                for (const field of checks) {
                    const text = contentMap[field];
                    if (text && regex.test(text)) {
                        matched = true;
                        matchVal = text.match(regex)?.[0] || '';
                        break;
                    }
                }
                if (matched) break;
            }
        }
        // Check domains
        if (rule.domains && domain) {
            if (rule.domains.some(d => domain === d || domain.endsWith('.' + d))) {
                 matched = true; matchVal = domain;
            }
            if (!matched && (checks.includes('body') || checks.includes('title'))) {
                 for (const d of rule.domains) {
                     if ((checks.includes('body') && body.includes(d)) || (checks.includes('title') && title.includes(d))) {
                         matched = true; matchVal = d; break;
                     }
                 }
            }
        }
        // Check domainsStartsWith
        if (rule.domainsStartsWith && domain) {
            if (rule.domainsStartsWith.some(d => domain.startsWith(d))) {
                matched = true; matchVal = domain;
            }
        }

        if (matched) {
            console.log(`Triggered Rule: ${rule.name} on ${post.id}`);
            await reddit.remove(post.id, rule.action === 'spam');
            if (rule.message) {
                const msg = rule.message.replace('{{author}}', author.name).replace('{{match}}', matchVal);
                const comment = await reddit.submitComment({ id: post.id, text: msg });
                await comment.distinguish(true);
            }
            return; // Stop processing
        }
    }

    // 3. Get User Karma
    // We fetch the user details to calculate total karma
    const user = await reddit.getUserById(author.id);
    if (!user) return;
    
    const totalKarma = (user.linkKarma || 0) + (user.commentKarma || 0);

    // 4. Determine Limit based on Tiers from Settings
    const tiersSetting = await settings.get('tiers');
    let tiers = [
        { maxKarma: 250, limit: 1 },
        { maxKarma: 500, limit: 2 },
        { maxKarma: null, limit: 4 },
    ];
    try {
        if (tiersSetting) {
            tiers = JSON.parse(tiersSetting as string);
        }
    } catch (e) {
        console.error("Failed to parse tiers setting, using default.", e);
    }

    let limit = 4;
    for (const tier of tiers) {
      const maxKarma = tier.maxKarma === null ? Infinity : tier.maxKarma;
      if (totalKarma < maxKarma) {
        limit = tier.limit;
        break;
      }
    }

    // 5. Check Post History (Rolling 24h window)
    const key = `post_history:${user.username}`;
    const now = Date.now();
    const oneDayMs = 24 * 60 * 60 * 1000;
    
    // Fetch existing timestamps from KV Store
    const historyData = await kvStore.get<number[]>(key);
    let timestamps = historyData || [];

    // Filter out posts older than 24h
    timestamps = timestamps.filter(ts => now - ts < oneDayMs);

    console.log(`User: ${user.username}, Karma: ${totalKarma}, Limit: ${limit}, Recent Posts: ${timestamps.length}`);

    if (timestamps.length >= limit) {
      // 6. Enforce Limit
      console.log(`Removing post ${post.id} by ${user.username}`);
      
      await reddit.remove(post.id, false);
      
      const comment = await reddit.submitComment({
        id: post.id,
        text: `Hi u/${user.username}, your post has been removed because you have reached your daily posting limit.\n\n` +
              `Your account has **${totalKarma} karma**, which limits you to **${limit} post(s)** per 24 hours.\n\n` +
              `Please try again tomorrow!`
      });
      
      if (comment) await comment.distinguish(true); // Sticky the comment
    } else {
      // 7. Log new post timestamp
      timestamps.push(now);
      await kvStore.put(key, timestamps);
    }
  },
});

export default Devvit;
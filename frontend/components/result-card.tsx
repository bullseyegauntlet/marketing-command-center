"use client";

import { useState } from "react";
import { type Post, formatRelativeTime } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ResultCardProps {
  post: Post;
  index?: number;
}

const platformConfig: Record<string, { label: string; dot: string; bg: string; text: string }> = {
  x: {
    label: "X",
    dot: "bg-gray-800",
    bg: "bg-gray-100",
    text: "text-gray-800",
  },
  slack: {
    label: "Slack",
    dot: "bg-violet-500",
    bg: "bg-violet-50",
    text: "text-violet-700",
  },
  reddit: {
    label: "Reddit",
    dot: "bg-orange-500",
    bg: "bg-orange-50",
    text: "text-orange-700",
  },
  linkedin: {
    label: "LinkedIn",
    dot: "bg-blue-600",
    bg: "bg-blue-50",
    text: "text-blue-700",
  },
};

const TRUNCATE_AT = 280;

/** Build a profile/entity URL based on platform and token type */
function buildLink(platform: string, type: "mention" | "hashtag" | "subreddit", value: string): string | null {
  const clean = value.replace(/^[@#]/, "");
  switch (platform) {
    case "x":
      if (type === "mention") return `https://x.com/${clean}`;
      if (type === "hashtag") return `https://x.com/hashtag/${clean}`;
      return null;
    case "reddit":
      if (type === "mention") return `https://www.reddit.com/user/${clean}`;
      if (type === "subreddit") return `https://www.reddit.com/r/${clean}`;
      if (type === "hashtag") return null;
      return null;
    case "linkedin":
      if (type === "mention") return `https://www.linkedin.com/search/results/people/?keywords=${encodeURIComponent(clean)}`;
      return null;
    default:
      return null;
  }
}

/** Parse post content into segments: plain text, @mentions, #hashtags, r/subreddits */
function parseContent(text: string, platform: string): React.ReactNode[] {
  // Match: @username, #hashtag, r/subreddit, u/username
  const regex = /(@[\w.]+|#[\w]+|r\/[\w]+|u\/[\w]+)/g;
  const parts: React.ReactNode[] = [];
  let last = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    const token = match[0];
    const start = match.index;

    // Push preceding plain text
    if (start > last) {
      parts.push(text.slice(last, start));
    }

    let href: string | null = null;
    let type: "mention" | "hashtag" | "subreddit" = "mention";

    if (token.startsWith("r/")) {
      type = "subreddit";
      href = `https://www.reddit.com/${token}`;
    } else if (token.startsWith("u/")) {
      type = "mention";
      href = `https://www.reddit.com/user/${token.slice(2)}`;
    } else if (token.startsWith("@")) {
      type = "mention";
      href = buildLink(platform, "mention", token);
    } else if (token.startsWith("#")) {
      type = "hashtag";
      href = buildLink(platform, "hashtag", token);
    }

    if (href) {
      parts.push(
        <a
          key={start}
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          className={cn(
            "font-medium transition-colors",
            type === "mention"
              ? "text-primary hover:text-primary/70"
              : "text-violet-500 hover:text-violet-400"
          )}
        >
          {token}
        </a>
      );
    } else {
      // No link available — still color it
      parts.push(
        <span
          key={start}
          className={type === "mention" ? "text-primary font-medium" : "text-violet-500 font-medium"}
        >
          {token}
        </span>
      );
    }

    last = start + token.length;
  }

  if (last < text.length) {
    parts.push(text.slice(last));
  }

  return parts;
}

export function ResultCard({ post, index = 0 }: ResultCardProps) {
  const [expanded, setExpanded] = useState(false);
  const platform = platformConfig[post.platform] ?? platformConfig.slack;
  const isLong = post.content.length > TRUNCATE_AT;
  const displayText =
    isLong && !expanded ? post.content.slice(0, TRUNCATE_AT).trimEnd() + "…" : post.content;

  const parsedContent = parseContent(displayText, post.platform);

  return (
    <div
      className="animate-card group relative bg-white border border-border rounded-2xl p-4 hover:border-primary/30 hover:shadow-md hover:shadow-primary/5 transition-all duration-200 cursor-default"
      style={{ animationDelay: `${Math.min(index * 35, 350)}ms` }}
    >
      {/* Header */}
      <div className="flex items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={cn("inline-flex items-center gap-1.5 text-xs font-semibold px-2 py-0.5 rounded-full", platform.bg, platform.text)}>
            <span className={cn("w-1.5 h-1.5 rounded-full", platform.dot)} />
            {platform.label}
          </span>
          {post.channel && (
            <span className="text-xs text-muted-foreground font-medium">#{post.channel}</span>
          )}
          <span className="text-sm font-medium text-foreground">@{post.author}</span>
        </div>
        <span className="text-xs text-muted-foreground whitespace-nowrap shrink-0">
          {formatRelativeTime(post.published_at)}
        </span>
      </div>

      {/* Content */}
      <p className="text-sm text-foreground/90 leading-relaxed whitespace-pre-wrap break-words">
        {parsedContent}
      </p>

      {isLong && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="mt-2 text-xs text-primary hover:text-primary/70 font-medium transition-colors"
        >
          {expanded ? "Show less ↑" : "Show more ↓"}
        </button>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between mt-3 pt-3 border-t border-border/60">
        <div className="flex items-center gap-3">
          {post.platform === "x" && (
            <>
              {post.likes !== undefined && post.likes > 0 && (
                <span className="text-xs text-muted-foreground">♥ {post.likes.toLocaleString()}</span>
              )}
              {post.retweets !== undefined && post.retweets > 0 && (
                <span className="text-xs text-muted-foreground">↩ {post.retweets.toLocaleString()}</span>
              )}
            </>
          )}
          {post.platform === "reddit" && (
            <>
              {post.likes !== undefined && post.likes > 0 && (
                <span className="text-xs text-muted-foreground">⬆ {post.likes.toLocaleString()}</span>
              )}
              {post.replies !== undefined && post.replies > 0 && (
                <span className="text-xs text-muted-foreground">💬 {post.replies.toLocaleString()}</span>
              )}
            </>
          )}
          {post.score !== undefined && (
            <span className="text-xs font-medium text-primary/70 bg-accent px-1.5 py-0.5 rounded-full">
              {Math.round(post.score * 100)}%
            </span>
          )}
        </div>
        <a
          href={post.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-primary hover:text-primary/70 font-semibold transition-colors flex items-center gap-1 opacity-0 group-hover:opacity-100"
          onClick={(e) => e.stopPropagation()}
        >
          Open ↗
        </a>
      </div>
    </div>
  );
}

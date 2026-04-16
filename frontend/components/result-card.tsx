"use client";

import { useState } from "react";
import { type Post, formatRelativeTime } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ResultCardProps {
  post: Post;
  index?: number;
}

const platformConfig: Record<string, { label: string; color: string; dim: string }> = {
  x:        { label: "X",        color: "rgba(255,255,255,0.7)", dim: "rgba(255,255,255,0.06)" },
  slack:    { label: "Slack",    color: "#9B8EF0",               dim: "rgba(155,142,240,0.08)" },
  reddit:   { label: "Reddit",   color: "#FF6B35",               dim: "rgba(255,107,53,0.08)"  },
  linkedin: { label: "LinkedIn", color: "#5B9BD5",               dim: "rgba(91,155,213,0.08)"  },
};

const TRUNCATE_AT = 280;

function buildLink(platform: string, type: "mention" | "hashtag" | "subreddit", value: string): string | null {
  const clean = value.replace(/^[@#]/, "");
  if (platform === "x") {
    if (type === "mention") return `https://x.com/${clean}`;
    if (type === "hashtag") return `https://x.com/hashtag/${clean}`;
  }
  if (platform === "reddit") {
    if (type === "mention") return `https://www.reddit.com/user/${clean}`;
    if (type === "subreddit") return `https://www.reddit.com/r/${clean}`;
  }
  if (platform === "linkedin" && type === "mention") {
    return `https://www.linkedin.com/search/results/people/?keywords=${encodeURIComponent(clean)}`;
  }
  return null;
}

function parseContent(text: string, platform: string): React.ReactNode[] {
  const regex = /(@[\w.]+|#[\w]+|r\/[\w]+|u\/[\w]+)/g;
  const parts: React.ReactNode[] = [];
  let last = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    const token = match[0];
    const start = match.index;

    if (start > last) parts.push(text.slice(last, start));

    let href: string | null = null;
    let isMention = true;

    if (token.startsWith("r/")) {
      href = `https://www.reddit.com/${token}`;
      isMention = false;
    } else if (token.startsWith("u/")) {
      href = `https://www.reddit.com/user/${token.slice(2)}`;
    } else if (token.startsWith("@")) {
      href = buildLink(platform, "mention", token);
    } else if (token.startsWith("#")) {
      href = buildLink(platform, "hashtag", token);
      isMention = false;
    }

    const className = cn(
      "font-medium transition-colors cursor-pointer",
      isMention ? "text-[#C09E5A] hover:text-[#D4B575]" : "text-[rgba(255,255,255,0.5)] hover:text-[rgba(255,255,255,0.8)]"
    );

    if (href) {
      parts.push(
        <a key={start} href={href} target="_blank" rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()} className={className}>
          {token}
        </a>
      );
    } else {
      parts.push(<span key={start} className={className}>{token}</span>);
    }

    last = start + token.length;
  }

  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

export function ResultCard({ post, index = 0 }: ResultCardProps) {
  const [expanded, setExpanded] = useState(false);
  const platform = platformConfig[post.platform] ?? platformConfig.slack;
  const isLong = post.content.length > TRUNCATE_AT;
  const displayText =
    isLong && !expanded ? post.content.slice(0, TRUNCATE_AT).trimEnd() + "…" : post.content;

  return (
    <div
      className="animate-card group relative border border-[#2B2B2B] bg-[#121212] p-4 transition-all duration-200 hover:border-[rgba(192,158,90,0.25)] hover:bg-[#151515]"
      style={{
        borderRadius: "4px",
        animationDelay: `${Math.min(index * 35, 350)}ms`,
      }}
    >
      {/* Subtle gold left accent on hover */}
      <div className="absolute left-0 top-0 bottom-0 w-px bg-[#C09E5A] opacity-0 group-hover:opacity-100 transition-opacity duration-200" style={{ borderRadius: "4px 0 0 4px" }} />

      {/* Header */}
      <div className="flex items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className="text-[10px] font-semibold px-2 py-0.5 tracking-wider uppercase"
            style={{
              color: platform.color,
              backgroundColor: platform.dim,
              borderRadius: "2px",
            }}
          >
            {platform.label}
          </span>
          {post.channel && (
            <span className="text-xs text-[rgba(255,255,255,0.3)] font-mono">#{post.channel}</span>
          )}
          <span className="text-sm font-medium text-[rgba(255,255,255,0.7)]">@{post.author}</span>
        </div>
        <span className="text-[11px] text-[rgba(255,255,255,0.25)] whitespace-nowrap shrink-0 tabular-nums">
          {formatRelativeTime(post.published_at)}
        </span>
      </div>

      {/* Content */}
      <p className="text-sm text-[rgba(255,255,255,0.75)] leading-relaxed whitespace-pre-wrap break-words">
        {parseContent(displayText, post.platform)}
      </p>

      {isLong && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="mt-2 text-xs text-[#C09E5A] hover:text-[#D4B575] font-medium transition-colors"
        >
          {expanded ? "Show less ↑" : "Show more ↓"}
        </button>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between mt-3 pt-3 border-t border-[#1e1e1e]">
        <div className="flex items-center gap-3">
          {post.platform === "x" && (
            <>
              {post.likes !== undefined && post.likes > 0 && (
                <span className="text-[11px] text-[rgba(255,255,255,0.3)]">♥ {post.likes.toLocaleString()}</span>
              )}
              {post.retweets !== undefined && post.retweets > 0 && (
                <span className="text-[11px] text-[rgba(255,255,255,0.3)]">↩ {post.retweets.toLocaleString()}</span>
              )}
            </>
          )}
          {post.platform === "reddit" && (
            <>
              {post.likes !== undefined && post.likes > 0 && (
                <span className="text-[11px] text-[rgba(255,255,255,0.3)]">⬆ {post.likes.toLocaleString()}</span>
              )}
              {post.replies !== undefined && post.replies > 0 && (
                <span className="text-[11px] text-[rgba(255,255,255,0.3)]">💬 {post.replies.toLocaleString()}</span>
              )}
            </>
          )}
          {post.score !== undefined && (
            <span className="text-[10px] font-medium text-[#C09E5A] bg-[rgba(192,158,90,0.1)] px-1.5 py-0.5" style={{ borderRadius: "2px" }}>
              {Math.round(post.score * 100)}% match
            </span>
          )}
        </div>
        <a
          href={post.source_url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="text-[11px] text-[rgba(255,255,255,0.25)] hover:text-[#C09E5A] font-medium transition-colors opacity-0 group-hover:opacity-100 flex items-center gap-1"
        >
          Open ↗
        </a>
      </div>
    </div>
  );
}

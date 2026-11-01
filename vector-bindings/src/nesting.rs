//! Bracket-depth guard run on caller-supplied VRL before the parser sees it.
//!
//! The VRL parser recurses per nesting level with no depth limit of its own,
//! and past a few thousand levels of (), {}, or [] it overflows even the VRL
//! stack and aborts the interpreter, which no Python `except` can catch.
//! Ordinary VRL never nests anywhere near the limit.
//!
//! Brackets are counted the way VRL's lexer sees them: string, raw string,
//! regex and timestamp literals and `#` comments carry no structure, so a
//! bracket inside one is neither counted nor allowed to close a real one.

/// Deepest bracket nesting a VRL program may use.
pub(crate) const MAX_VRL_NESTING_DEPTH: usize = 64;

/// Reject VRL source whose brackets nest deeper than `MAX_VRL_NESTING_DEPTH`.
pub(crate) fn check_nesting_depth(vrl_code: &str) -> Result<(), String> {
    let max_depth = max_bracket_depth(vrl_code);
    if max_depth > MAX_VRL_NESTING_DEPTH {
        return Err(format!(
            "VRL source nests {max_depth} levels deep, exceeding the {MAX_VRL_NESTING_DEPTH}-level limit"
        ));
    }
    Ok(())
}

/// The deepest structural bracket nesting in `source`.
///
/// Closers are not matched to their opener's kind: a mismatch is a parse
/// error the compiler reports, and counting every kind together can only
/// overstate the depth.
fn max_bracket_depth(source: &str) -> usize {
    let mut chars = source.chars().peekable();
    let mut depth: usize = 0;
    let mut max_depth: usize = 0;
    while let Some(c) = chars.next() {
        match c {
            '(' | '{' | '[' => {
                depth += 1;
                max_depth = max_depth.max(depth);
            }
            ')' | '}' | ']' => depth = depth.saturating_sub(1),
            '"' => skip_quoted(&mut chars, '"'),
            '#' => while chars.next_if(|&c| c != '\n').is_some() {},
            // `r'`, `s'` and `t'` open a literal only at the start of a token,
            // so `bars'` stays the identifier `bars` and a stray quote.
            'r' | 's' | 't' if chars.peek() == Some(&'\'') => {
                chars.next();
                skip_quoted(&mut chars, '\'');
            }
            c if is_ident_continue(c) => {
                while chars.next_if(|&c| is_ident_continue(c)).is_some() {}
            }
            _ => {}
        }
    }
    max_depth
}

/// Advance past a literal's closing `close`, stepping over backslash escapes.
///
/// An unterminated literal consumes the rest of the source, and the compiler
/// rejects it.
fn skip_quoted(chars: &mut std::iter::Peekable<std::str::Chars<'_>>, close: char) {
    while let Some(c) = chars.next() {
        if c == '\\' {
            chars.next();
        } else if c == close {
            return;
        }
    }
}

/// VRL's own identifier-continue set, digits included.
fn is_ident_continue(c: char) -> bool {
    matches!(c, '@' | '_' | 'a'..='z' | 'A'..='Z' | '0'..='9')
}

#[cfg(test)]
mod tests {
    use super::*;

    const DEEP: usize = MAX_VRL_NESTING_DEPTH + 6;

    #[test]
    fn nesting_at_the_limit_is_accepted_and_one_past_it_is_not() {
        for (depth, accepted) in [
            (MAX_VRL_NESTING_DEPTH, true),
            (MAX_VRL_NESTING_DEPTH + 1, false),
        ] {
            let vrl = format!("{}{}{}", "(".repeat(depth), "true", ")".repeat(depth));
            assert_eq!(check_nesting_depth(&vrl).is_ok(), accepted, "depth {depth}");
        }
    }

    #[test]
    fn brackets_inside_literals_and_comments_are_not_counted() {
        for vrl in [
            format!(".x = \"{}\"", "(".repeat(DEEP)),
            format!(".x = \"\\\"{}\"", "[".repeat(DEEP)),
            format!(".x = s'{}'", "{".repeat(DEEP)),
            format!(".x = s'\\'{}'", "(".repeat(DEEP)),
            format!(".x = t'{}'", "(".repeat(DEEP)),
            format!(".x = match(.message, r'{}')", "(".repeat(DEEP)),
            format!("# {}\n.x = 1", "(".repeat(DEEP)),
            format!(".\"{}\" = 1", "[".repeat(DEEP)),
        ] {
            assert!(check_nesting_depth(&vrl).is_ok(), "rejected {vrl:?}");
        }
    }

    #[test]
    fn closing_brackets_inside_literals_do_not_hide_real_nesting() {
        for vrl in [
            format!(".x = {}1{}", "[\")\", ".repeat(DEEP), "]".repeat(DEEP)),
            format!(".x = {}1{}", "[s')', ".repeat(DEEP), "]".repeat(DEEP)),
            format!(".x = {}1{}", "[ # )\n".repeat(DEEP), "]".repeat(DEEP)),
        ] {
            assert!(check_nesting_depth(&vrl).is_err(), "accepted {vrl:?}");
        }
    }

    #[test]
    fn literal_prefixes_inside_identifiers_do_not_open_a_literal() {
        for prefix in ["bars'", "1r'", "post'"] {
            let vrl = format!(".x = {prefix}{}1{}", "(".repeat(DEEP), ")".repeat(DEEP));
            assert!(check_nesting_depth(&vrl).is_err(), "accepted {vrl:?}");
        }
    }

    #[test]
    fn an_unterminated_literal_ends_the_count() {
        let vrl = format!("{}\"{}", "(".repeat(3), "(".repeat(DEEP));
        assert_eq!(max_bracket_depth(&vrl), 3);
    }
}

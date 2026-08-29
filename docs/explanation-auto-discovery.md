# Why there are 96 Vector classes that do nothing

The extension exports a class for nearly every public type in Vector's event
and common modules - `LogEvent`, `Metric`, `EventStatus`, `ComponentKey`,
and 90-odd more. None of them is a binding to the Rust type it is named
after. This explains where they come from and why they look like an API when
they are not.

## The mechanism

`vector-bindings/build.rs` runs at compile time and walks two directories of
a sibling upstream Vector checkout:

```rust
PathBuf::from("../vector/lib/vector-core/src/event"),
PathBuf::from("../vector/lib/vector-common/src"),
```

For every `.rs` file it finds, it parses the file with `syn` and collects
every `pub struct` and `pub enum` at the top level. Names starting with `_`
are dropped, and three are hard-skipped because they collide with types the
crate already uses: `Secrets`, `BTreeMap`, `HashMap`. The results are
deduplicated by name, first occurrence wins.

It then GENERATES Rust source - one `#[pyclass]` per name - writes it to
`OUT_DIR/auto_bindings.rs`, and `lib.rs` splices it in with `include!`. A
generated `register_all_auto_bindings` adds every class to the module and
sets `__auto_count__`.

On the build this was written against:

```
../vector/lib/vector-core/src/event - 46 APIs
../vector/lib/vector-common/src     - 50 APIs
Discovered 96 unique Vector APIs across all modules
```

Read the number from your own build. It moves whenever upstream Vector adds
or removes a public type, and it is zero if you have no `vector/` checkout.

## What actually gets generated

For a struct, the generated class has one field, `data`, of type `String`.
It has no relationship to the real struct's fields:

```python
>>> from vectordotdev._bindings import LogEvent
>>> e = LogEvent()
>>> [x for x in dir(e) if not x.startswith('_')]
['data']
>>> e.data = 'anything at all'
>>> e.data
'anything at all'
```

`LogEvent` in Vector is a log event with a value tree and metadata. Here it
is a box holding one string that you set yourself.

For an enum, the variant NAMES survive as lowercase staticmethods, and the
value is the variant name as a string:

```python
>>> from vectordotdev._bindings import EventStatus
>>> [x for x in dir(EventStatus) if not x.startswith('_')]
['delivered', 'dropped', 'errored', 'recorded', 'rejected']
>>> EventStatus.dropped()
EventStatus::Dropped
```

That is closer to useful - the variant list is real, harvested from upstream
source. But there is still nothing behind it. You cannot pass one to
anything, and nothing returns one.

## So what is it good for

As it stands, nothing you should build on. The classes are name-shaped
evidence that a type exists upstream, and that is the whole of it. This is
[issue #15](https://github.com/hyperi-io/vectordotdev/issues/15).

The reason it looks impressive and is not: a count of 96 exposed classes
reads like API coverage, and every doc that quotes a count is quoting the
number of PLACEHOLDERS generated, not the number of types you can use. The
real API is five things - `execute_vrl`, `validate_vrl`,
`get_vrl_performance`, `Vector`, `VrlResult` - all hand-written in
`lib.rs`, all covered by tests. See
[reference-python-api.md](reference-python-api.md).

## Why the count in old docs disagrees with the count in your build

Three reasons, and they compound:

- The count changes with upstream Vector. It is whatever is public in those
  two directories on the day you build.
- It changes with the search paths. Adding a directory to `search_paths` in
  `build.rs` changes it immediately.
- It is zero when `vector/` is missing, and the build still succeeds. See
  [how-to-build-and-test.md](how-to-build-and-test.md#the-vector-checkout).

Numbers between 45 and 96 appear in various older files in this repo and
none of them agree. Treat every written-down count as stale, including the
one above, and read the `Discovered N unique Vector APIs` warning line from
the build in front of you.

## If you wanted to make it real

Generating a placeholder per name is the easy 90% that delivers 0%. A real
binding needs the type's fields, its conversions to and from Python, and a
decision per type about whether exposing it makes sense at all - which is a
design question per type, not something a `syn` walk can answer. The current
generator cannot get there incrementally, so the honest options are to build
real bindings for the handful of types that earn one, or to drop the
generated surface entirely.

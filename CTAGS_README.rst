TAG FILE FORMAT
===============

When not running in etags mode, each entry in the tag file consists of a
separate line, each looking like this in the most general case::

  tag_name<TAB>file_name<TAB>ex_cmd;"<TAB>extension_fields

The fields and separators of these lines are specified as follows:

#. Tag name
#. Single tab character
#. Name of the file in which the object associated with the tag is located
#. Single tab character
#. EX command used to locate the tag within the file; generally a search
   pattern (either ``/pattern/`` or ``?pattern?``) or line number (see 
   ``−−excmd``). 
   Tag file format 2 (see ``−−format``) extends this EX command under certain
   circumstances to include a set of extension fields (described below)
   embedded in an EX comment immediately appended to the EX command, which
   leaves it backward-compatible with original ``vi(1)`` implementations.

A few special tags are written into the tag file for internal purposes. These
tags are composed in such a way that they always sort to the top of the file.
Therefore, the first two characters of these tags are used a magic number to
detect a tag file for purposes of determining whether a valid tag file is
being overwritten rather than a source file. Note that the name of each source
file will be recorded in the tag file exactly as it appears on the command
line.

Therefore, if the path you specified on the command line was relative to the
current directory, then it will be recorded in that same manner in the tag
file. See, however, the ``−−tag−relative`` option for how this behavior can be
modified.

Extension fields are tab-separated key-value pairs appended to the end of the
EX command as a comment, as described above. These key value pairs appear in
the general form ``key:value``. Their presence in the lines of the tag file
are controlled by the ``−−fields`` option. The possible keys and the meaning
of their values are as follows:

access
  Indicates the visibility of this class member, where value is specific to
  the language.

file
  Indicates that the tag has file-limited visibility. This key has no
  corresponding value.

kind
  Indicates the type, or kind, of tag. Its value is either one of the
  corresponding one-letter flags described under the various 
  ``−−<LANG>−kinds`` options above, or a full name. It is permitted (and is,
  in fact, the default) for the key portion of this field to be omitted. The
  optional behaviors are controlled with the ``−−fields`` option.

implementation
  When present, this indicates a limited implementation (abstract vs. concrete)
  of a routine or class, where value is specific to the language ("virtual" or
  "pure virtual" for C++; "abstract" for Java).

inherits
  When present, value is a comma-separated list of classes from which this
  class is derived (i.e. inherits from).

signature
  When present, value is a language-dependent representation of the
  signature of a routine. A routine signature in its complete form specifies
  the return type of a routine and its formal argument list. This extension
  field is presently supported only for C-based languages and does not
  include the return type.

In addition, information on the scope of the tag definition may be available,
with the key portion equal to some language-dependent construct name and its
value the name declared for that construct in the program. This scope entry
indicates the scope in which the tag was found. For example, a tag generated
for a C structure member would have a scope looking like ``struct:myStruct``.
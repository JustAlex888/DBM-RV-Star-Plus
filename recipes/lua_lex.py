import re
def lex(data, strict=True):
    i = 0
    n = len(data)
    out = []

    def long_end(pos):
        m = re.match(b'\\[(=*)\\[', data[pos:])
        if not m:
            return None
        closing = b']' + m[1] + b']'
        end = data.find(closing, pos + len(m[0]))
        if end < 0:
            if strict:
                raise AssertionError(('unclosed longblock', pos))
            return n
        return end + len(closing)
    while i < n:
        start = i
        c = data[i:i + 1]
        if c in b' \t\r\n\x0b\x0c':
            i += 1
            while i < n and data[i:i + 1] in b' \t\r\n\x0b\x0c':
                i += 1
            kind = 'SPACE'
        elif data[i:i + 2] == b'--':
            end = long_end(i + 2)
            if end is None:
                end = data.find(b'\n', i + 2)
                end = n if end < 0 else end
            i = end
            kind = 'COMMENT'
        elif c in (b'"', b"'"):
            quote = c
            i += 1
            while i < n:
                if data[i:i + 1] == b'\\':
                    i += 2
                elif data[i:i + 1] == quote:
                    i += 1
                    break
                else:
                    i += 1
            else:
                raise AssertionError(('unclosed quote', start))
            kind = 'STRING'
        elif c == b'[' and (end := long_end(i)) is not None:
            i = end
            kind = 'STRING'
        elif (m := re.match(b'[A-Za-z_][A-Za-z_0-9]*', data[i:])):
            i += len(m[0])
            kind = 'IDENT'
        elif (m := re.match(b'(?:0[xX][0-9A-Fa-f]+|(?:\\d+\\.?\\d*|\\.\\d+)(?:[eE][+-]?\\d+)?)', data[i:])):
            i += len(m[0])
            kind = 'NUMBER'
        else:
            match = next((x for x in (b'...', b'..', b'==', b'~=', b'<=', b'>=') if data.startswith(x, i)), None)
            i += len(match) if match else 1
            kind = 'SYMBOL'
        out.append((kind, start, i, data[start:i]))
    assert b''.join((t[3] for t in out)) == data
    return out

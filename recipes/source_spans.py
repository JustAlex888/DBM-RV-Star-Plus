"""Read source expressions from pinned user inputs, never embedded encounter bodies.
These helpers edit source structure and formatting. No target file is consulted.
"""
import re
from lua_lex import lex

def function_text(text,name):
    match=re.search(r'(?m)^(?:local )?function (?:mod:)?'+re.escape(name)+r'\(',text)
    assert match,name
    raw=text[match.start():].encode('utf8');ts=[t for t in lex(raw)if t[0]not in ('SPACE','COMMENT')];stack=[]
    for kind,a,b,value in ts:
        if value==b'function':stack.append([value,False])
        elif value in (b'if',b'repeat'):stack.append([value,False])
        elif value in (b'for',b'while'):stack.append([value,True])
        elif value==b'do':
            if stack and stack[-1][1]:stack[-1][1]=False
            else:stack.append([value,False])
        elif value in (b'end',b'until'):
            stack.pop()
            if not stack:return raw[:b].decode('utf8')
    raise AssertionError('unclosed source function: '+name)

def move_aura_branch(text,spell):
    # Extract condition and body from the unreachable donor elseif, then move
    # them into its earlier matching aura branch. Keep exact accepted whitespace.
    pattern=r'(?m)^(\t)elseif spellId == '+str(spell)+r' and ([^\n]+) then\n((?:\t\t[^\n]*\n)+)'
    found=list(re.finditer(pattern,text));assert len(found)==1,(spell,len(found));m=found[0]
    condition=m[2];body=m[3];insert='\t\tif '+condition+' then\n'+''.join('\t'+line for line in body.splitlines(True))+'\t\tend\n'
    # Preserve the newline after the removed branch exactly as the former adapter.
    text=text[:m.start()]+text[m.end()-1:]
    pattern=r'(?m)^(\tif spellId == '+str(spell)+r' then\n)'
    text,n=re.subn(pattern,lambda m:m[1]+insert,text,count=1);assert n==1
    return text

def first_branch_calls(text,name):
    body=function_text(text,name).splitlines();result=[];active=False
    for line in body[1:]:
        stripped=line.strip()
        if not active and stripped.startswith('if '):active=True;continue
        if active and (stripped=='end' or stripped.startswith(('else','elseif'))):break
        if active and stripped and not stripped.startswith('--'):result.append(stripped)
    assert result,(name,'missing source actions')
    return result

def format_function(text):
    # Only used on the selected simple S01 helper. Comments are deliberately
    # omitted; semantic statements remain source-derived and are not replaced.
    result=[];depth=0
    for original in text.splitlines():
        line=original.split('--',1)[0].strip()
        if not line:continue
        if line=='end' or line=='else' or line.startswith('elseif '):depth-=1
        assert depth>=0,line
        result.append(' '*depth+line)
        if line.startswith(('local function ','function ','if ','elseif '))or line=='else':depth+=1
    assert depth==0
    return '\n'.join(result)+'\n'

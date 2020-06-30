import re
import os
import time
import hashlib
from collections import namedtuple
import subprocess

pattern_dict = {
    'var_expr': r'[a-zA-Z_]+\w* *(?=[=<>\+\-\*/;\),\]&|])',
    'for_expr': r'(for\s*\(.*\) *\{[^}]*\}*?\})',
    'fun_expr': r'\w+(?=[(].*)',
    'anno_expr': r'(?://[^\n]*|/\*(?:(?!\*/).)*\*/)',
    'arr1_expr': r'[a-zA-Z_]+\w*(?=\[[^\]]+\][\=><\+\-\*\/;,\)&|\]])',
    'arr2_expr': r'[a-zA-Z_]+\w*(?=\[[^\]]+\]\[[^\]]+\][\=><\+\-\*\/;,\)&|\]])',
    'arr3_expr': r'[a-zA-Z_]+\w*(?=\[[^\]]+\]\[[^\]]+\]\[[^\]]+\][\=><\+\-\*\/;,\)&|\]])',
    'arr4_expr': r'[a-zA-Z_]+\w*(?=\[[^\]]+\]\[[^\]]+\]\[[^\]]+\]\[[^\]]+\][\=><\+\-\*\/;,\)&|\]])',
    'arr5_expr': r'[a-zA-Z_]+\w*(?=\[[^\]]+\]\[[^\]]+\]\[[^\]]+\]\[[^\]]+\]\[[^\]]+\][\=><\+\-\*\/;,\)&|\]])',
    'arr6_expr': r'[a-zA-Z_]+\w*(?=\[[^\]]+\]\[[^\]]+\]\[[^\]]+\]\[[^\]]+\]\[[^\]]+\]\[[^\]]+\][\=><\+\-\*\/;,\)&|\]])',
    'poi_expr': r'(?<=[=<>\+\-\*/\(,;]\*)[a-zA-Z_]+\w*\s*(?=[=\+\-\*/;,])'
}

type_list = ['void', 'int', 'double', 'float', 'bool', 'char', 'wchar_t', 'short', 'long', 'enum', 'const', 'signed',
             'unsigned', 'static', 'mutable', 'vector<', 'public', 'private']

keyword_list = ['true', 'false', 'for', 'if', 'break', 'while', 'else', 'switch', 'case', 'return', 'continue', 'class']

FUN = namedtuple('Function', 'fun_name fun_define fun_lines')
FOR_LINE = namedtuple('For_part', 'lines fun_name idx')



def read_file(file_path, filename):
    """从文件按行加载内容，返回字符串列表file_lines=['..',...''],不保留空行"""
    file_lines = []
    with open(file_path + filename, 'r', encoding='ISO-8859-1') as f:
        temp = f.read()
        f.close()
    pattern = re.compile(pattern_dict['anno_expr'], re.DOTALL)
    res = pattern.findall(temp)
    for s in res:
        temp = temp.replace(s, "", 1)
    for x in temp.split("\n"):
        if x.strip() == "" or x.strip() == "\n" or '#include' in x or '# include ' in x or 'using namespace' in x or '#pragma' in x:
            continue
        else:
            file_lines.append(x.strip())
    return file_lines



def gen_header():

    with open("header.cpp", 'r', encoding='ISO-8859-1') as f:
        header = f.read()
        f.close()
    return header


def find_last(string, str):
    last_position = -1
    while True:
        position = string.find(str, last_position + 1)
        if position == -1:
            return last_position
        last_position = position


def find_funs(file_lines):
    fun_list = []
    pattern = re.compile(pattern_dict['fun_expr'], re.DOTALL)
    fun_flag = False
    define_flag = False
    define_begin = 0
    begin = 0
    fun_lines = ""
    fun_name = ""
    fun_define = ""
    for line in file_lines:
        row = line.split(" ")
        if row[0] in type_list:
            try:
                rst = pattern.findall(str(row[1]))
            except IndexError:
                continue

            if len(rst) != 0:
                fun_name = rst[0]
                define_flag = True
                fun_flag = True
        if define_flag:
            if '(' in line:
                define_begin += line.count('(')
            if ')' in line:
                define_begin -= line.count(')')
                if define_begin == 0:
                    define_flag = False
                    fun_define += line[0:find_last(line, ')') + 1].strip()
            if define_begin != 0:
                fun_define += line.strip()
        if fun_flag:
            if len(fun_lines) != 0:
                fun_lines += "\n" + line
            else:
                fun_lines += line
            if '{' in line:
                begin += line.count('{')
            if '}' in line:
                begin -= line.count('}')
                if begin == 0:
                    fun_flag = False
                    fun_list.append(FUN(fun_name, fun_define, fun_lines))
                    fun_lines = ""
                    fun_name = ""
                    fun_define = ""
    return fun_list


def extract_for(file_lines, fun_list):
    new_code = []
    new_file = "\n".join(file_lines[:])
    for_part = ""
    begin = 0
    flag = False
    if len(fun_list) != 0:
        for i in range(len(fun_list)):
            fun = fun_list[i]
            fun_lines = fun.fun_lines.split("\n")
            new_file = new_file.replace(fun.fun_lines, "\n" + fun.fun_define + ";\n")
            idx = 1000
            for line in fun_lines:
                if "for(" in line or 'for (' in line:
                    flag = True
                    if len(for_part) != 0:
                        for_part += "\n" + line
                    else:
                        for_part += line
                    if "{" in line:
                        begin += str(line).count('{', 0, len(line))
                    if "}" in line:
                        begin -= str(line).count('}', 0, len(line))
                        # 有打括号for一行就结束了
                        if begin == 0:
                            new_code.append(
                                FOR_LINE("#pragma scop\n" + for_part + "\n#pragma endscop", fun.fun_name, idx))
                            fun_list[i] = FUN(fun_list[i].fun_name, fun_list[i].fun_define,
                                              fun_list[i].fun_lines.replace(for_part, "//loop" + str(idx) + "\n"))
                            idx += 1
                            for_part = ""
                            flag = False
                    # 无大括号for一行结束
                    if begin == 0 and line[-1] == ';':
                        new_code.append(
                            FOR_LINE("#pragma scop\n" + for_part + "\n#pragma endscop", fun.fun_name, idx))
                        fun_list[i] = FUN(fun_list[i].fun_name, fun_list[i].fun_define,
                                          fun_list[i].fun_lines.replace(for_part, "//loop" + str(idx) + "\n"))
                        idx += 1
                        for_part = ""
                        flag = False
                    continue
                if flag:
                    if "{" in line:
                        begin += str(line).count('{', 0, len(line))
                    if "}" in line:
                        begin -= str(line).count('}', 0, len(line))
                if begin != 0:
                    if len(for_part) != 0:
                        for_part += "\n" + line
                    else:
                        for_part += line
                elif flag:
                    if len(for_part) != 0:
                        for_part += "\n" + line
                    else:
                        for_part += line
                    new_code.append(
                        FOR_LINE("#pragma scop\n" + for_part + "\n#pragma endscop", fun.fun_name, idx))
                    fun_list[i] = FUN(fun_list[i].fun_name, fun_list[i].fun_define,
                                      fun_list[i].fun_lines.replace(for_part, "//loop" + str(idx) + "\n"))
                    idx += 1
                    for_part = ""
                    flag = False
    else:
        for_idx = 1000
        for line in file_lines:
            if "for(" in line or 'for (' in line:
                flag = True
                for_part = for_part + line + "\n"
                if "{" in line:
                    begin += str(line).count('{', 0, len(line))
                if "}" in line:
                    begin -= str(line).count('}', 0, len(line))

                    if begin == 0:
                        new_code.append(
                            FOR_LINE("#pragma scop\n" + for_part + "\n#pragma endscop", None, for_idx))
                        new_file = new_file.replace(for_part, "//loop" + str(for_idx) + "\n")
                        for_idx += 1
                        for_part = ""
                        flag = False

                if begin == 0 and line[-1] == ';':
                    new_code.append(
                        FOR_LINE("#pragma scop\n" + for_part + "\n#pragma endscop", None, for_idx))
                    new_file = new_file.replace(for_part, "//loop" + str(for_idx) + "\n")
                    for_idx += 1
                    for_part = ""
                    flag = False
                continue
            if flag:
                if "{" in line:
                    begin += str(line).count('{', 0, len(line))
                if "}" in line:
                    begin -= str(line).count('}', 0, len(line))
            if begin != 0:
                for_part = for_part + line + "\n"
            elif flag:
                for_part = for_part + line
                new_code.append(
                    FOR_LINE("#pragma scop\n" + for_part + "\n#pragma endscop", None, for_idx))
                new_file = new_file.replace(for_part, "//loop" + str(for_idx) + "\n")
                for_idx += 1
                for_part = ""
                flag = False
    return new_code, new_file, fun_list



def gen_new_code(file_path, file_name):
    file_list = []

    file_lines = read_file(file_path, file_name)

    fun_list = find_funs(file_lines)

    for_part_list, new_file, fun_list = extract_for(file_lines, fun_list)
    if len(for_part_list) == 0:
        return file_list

    if len(fun_list) == 0:
        for for_part in for_part_list:
            vars = get_for_var(for_part)
            header, var_define = get_define(vars)
            code = header + "int main(){\n" + var_define + new_file.replace("//loop" + str(for_part.idx),
                                                                            for_part.lines) + "\nreturn 0;\n}"
            filename = generate_file_name(code + str(time.time()))
            file_list.append(filename)
            with open('../data/pre_data/after_extract/' + filename, "w", encoding='utf-8') as f:
                f.write(code)
                f.close()
    else:

        header = gen_header()

        for for_part in for_part_list:
            code = header + "\n"
            fun_name = for_part.fun_name
            for fun in fun_list:
                if fun.fun_name == fun_name:

                    code += new_file.replace(fun.fun_define + ";",
                                             fun.fun_lines.replace("//loop" + str(for_part.idx), for_part.lines))
                    filename = generate_file_name(code + str(time.time()))
                    file_list.append(filename)
                    with open('../data/pre_data/after_extract/' + filename, "w", encoding='utf-8') as f:
                        f.write(code)
                        f.close()
    print("文件：%s    共生成新文件：%s 个" % (file_name, len(file_list)))
    return file_list



def generate_file_name(instance_str):
    """generate filename according to instance_str"""
    byte_obj = bytes(instance_str, 'utf-8')
    fname = hashlib.shake_128(byte_obj).hexdigest(5)
    fname = "{}.cpp".format(fname)
    return fname


def pluto_data_gen(file_list):
    error_list = []
    cmd = './polycc ../data/pre_data/after_extract/%s ' \
          '--noprevector --tile --parallel --innerpar --lbtile ' \
          '-o %s/%s'
    pluto_list = []
    i = 0
    for clazz in file_list:
        cmd1 = cmd % (clazz, '../data/pre_data/after_pluto', clazz)
        a = subprocess.run(cmd1, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if a.returncode == 0:
            pluto_list.append(clazz)
        else:
            error_list.append(clazz + "\n" + bytes.decode(a.stderr) + "=" * 50 + "\n")
        i += 1
        print("分析代码：    %s / %s ..." % (str(i), str(len(file_list))))
    with open('../log/pluto_error.log', "a+", encoding='utf-8') as f:
        f.write("\n".join(error_list))
        f.close()
    return pluto_list, error_list



def classify(pluto_list):
    cmd = 'cp ../data/pre_data/after_extract/%s ../data/handled/%s/%s'
    for clazz in pluto_list:
        with open("../data/pre_data/after_pluto/" + clazz, "r") as f:
            code = f.read()
            f.close()
        if "#pragma omp parallel" in code:
            cmd1 = cmd % (clazz, "parallel", clazz)
        else:
            cmd1 = cmd % (clazz, "unparallel", clazz)
        subprocess.call(cmd1, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def compile_data():
    cmds = [
        r"clang++ -S -emit-llvm -std=c++11 -O0 -march=native ../data/handled/%s/%s -o ../data/IR/%s/%s.ll",
        # r"clang++ -S -emit-llvm -std=c++11 -O0 -ffast-math -march=native ../data/handled/%s/%s -o ../data/IR/%s/%s.ll"
    ]
    parallel_error_list = []
    unparallel_error_list = []
    classlist = [f for f in os.listdir("../data/handled/parallel")]
    for i in range(0, len(cmds)):
        for clazz in classlist:
            cmd = cmds[i] % ("parallel", clazz, "1", clazz + "_" + str(i))
            a = subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            if a.returncode == 0:
                pass
            else:
                parallel_error_list.append(clazz + "\n" + bytes.decode(a.stderr) + "=" * 50)
        if i % 10 == 0:
            print("编译可并行代码：\t%s / %s ..." % (str(i), str(len(classlist))))
            time.sleep(0.1)

    classlist = [f for f in os.listdir("../data/handled/unparallel")]
    for i in range(0, len(cmds)):
        for clazz in classlist:
            cmd = cmds[i] % ("unparallel", clazz, "2", clazz + "_" + str(i))
            a = subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            if a.returncode == 0:
                pass
            else:
                unparallel_error_list.append(clazz + "\n" + bytes.decode(a.stderr) + "=" * 50)
        if i % 10 == 0:
            print("编译不可并行代码：\t%s / %s ..." % (str(i), str(len(classlist))))
            time.sleep(0.1)
    with open('../log/comp_error.log', "a+", encoding='utf-8') as f:
        f.write("\n" + "*" * 50 + "ParallelError" + "*" * 50 + "\n" +
                "\n".join(parallel_error_list) + "\n" + "*" * 50 + "Unparallel" + "*" * 50 + "\n" + "\n".join(
            unparallel_error_list))
        f.close()
    return parallel_error_list, unparallel_error_list


def clean_dir():
    # prefix = time.strftime('%Y-%m-%d-%H:%M:%S', time.localtime(time.time()))
    # zip = "zip -r ../backup/%s_data.zip ../data" % prefix
    clean = [
        r"rm -rf ../data/handled/*/*",
        r"rm -rf ../data/IR/*/*",
        r"rm -rf ../data/IR_processed/*/*",
        r"rm -rf ../data/pre_data/*/*",
        r"rm -rf ../data/unhandle/*/*",
        r"rm -rf ../log/*"
    ]
    # subprocess.call(zip, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for cl in clean:
        subprocess.call(cl, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def get_for_var(for_part):
    for_part = str(for_part).replace(" ", "")

    vars = []

    pattern = re.compile(pattern_dict['var_expr'])
    vars.append(set(pattern.findall(str(for_part))))

    pattern = re.compile(pattern_dict['arr1_expr'])
    vars.append(set(pattern.findall(str(for_part))))

    pattern = re.compile(pattern_dict['arr2_expr'])
    vars.append(set(pattern.findall(str(for_part))))

    pattern = re.compile(pattern_dict['arr3_expr'])
    vars.append(set(pattern.findall(str(for_part))))

    pattern = re.compile(pattern_dict['arr4_expr'])
    vars.append(set(pattern.findall(str(for_part))))

    pattern = re.compile(pattern_dict['arr5_expr'])
    vars.append(set(pattern.findall(str(for_part))))

    pattern = re.compile(pattern_dict['arr6_expr'])
    vars.append(set(pattern.findall(str(for_part))))

    pattern = re.compile(pattern_dict['poi_expr'])
    vars.append(set(pattern.findall(str(for_part))))

    for var in vars[7]:
        if var in vars[0]:
            vars[0].remove(var)
            continue
    for var in keyword_list:
        if var in vars[0]:
            vars[0].remove(var)
            continue
    for var in type_list:
        if var in vars[0]:
            vars[0].remove(var)
            continue


    for i in range(2, 7):
        for var in vars[i]:
            if var in vars[i - 1]:
                vars[i - 1].remove(var)
    return vars


def get_define(vars):

    with open("header.cpp", 'r', encoding='ISO-8859-1') as f:
        header = f.read()
        f.close()
    var_define = ""
    for var in vars[0]:
        var_define = var_define + 'int ' + var + '= 100' + ';\n'

    for i in range(1, len(vars) - 1):
        if len(vars[i]) != 0:
            for var in vars[i]:
                var_define = var_define + 'int ' + var + '[101]' * i + ';\n'

    for var in vars[7]:
        var_define = var_define + 'int *' + var + ';\n'
    return header, var_define


def process_ir():
    out_path = "../data/IR_processed/"
    for i in range(1, 3):
        classlist = [x for x in os.listdir("../data/IR/" + str(i))]
        for clazz in classlist:
            ir = []
            with open("../data/IR/" + str(i) + "/" + clazz, 'r', encoding='ISO-8859-1') as f:
                temp = f.readlines()
                f.close()
            flag = False
            for line in temp:
                if "; <label>:" in line:
                    flag = True
                    ir.append(line)
                    continue
                if flag:
                    if line.strip() == "" or line.strip() == "\n" or 'ret' in line or '}' in line:
                        flag = False
                    else:
                        ir.append(line)
            if len(ir) == 0:
                continue
            with open(out_path + str(i) + "/" + clazz, 'w', encoding='utf-8') as f:
                f.write("".join(ir))
                f.close()

"""Idempotently install a broad, local computer-science library and practice bank."""
from pathlib import Path
import asyncio,json,sys
from dotenv import load_dotenv
ROOT=Path(__file__).resolve().parents[1];load_dotenv(ROOT/'backend'/'.env');sys.path.insert(0,str(ROOT/'backend'))
from app import core
from app.document.parser import chunks,Page
from app.rag.store import index_document,close_clients

TOPICS={
'计算机系统与组成原理':'''# 计算机系统与组成原理
## 信息表示
计算机使用二进制表示信息。位是最小数据单位，字节通常由8位组成。无符号整数直接按位权展开；补码让加减法共用运算电路，并只有一个零。定点数精确表示有限范围内的整数，小数通常使用 IEEE 754 浮点格式，包含符号位、阶码和尾数，运算可能产生舍入误差。
## 冯·诺依曼结构
经典计算机由运算器、控制器、存储器、输入设备和输出设备组成，程序和数据以同等地位存入存储器。CPU 主要包含运算器、控制器、寄存器和高速缓存。指令周期通常经历取指、译码、执行和写回。
## 存储层次
寄存器、缓存、内存和外存构成由快到慢、由小到大的层次。局部性原理包括时间局部性与空间局部性，是缓存有效的基础。缓存未命中时需要从更低层读取。虚拟存储通过页表把虚拟地址映射为物理地址，TLB 缓存常用地址转换。
## 输入输出
程序查询会占用 CPU 等待设备；中断允许设备完成后通知处理器；DMA 可在设备与内存间批量传输，减少 CPU 搬运数据的负担。''',
'数据结构与算法':'''# 数据结构与算法
## 复杂度
时间复杂度描述输入规模增大时基本操作数量的增长趋势。常见数量级依次为 O(1)、O(log n)、O(n)、O(n log n)、O(n²)。空间复杂度衡量额外存储。大 O 给出渐进上界，分析时通常关注最坏情况，同时结合实际常数与数据分布。
## 线性结构
数组支持 O(1) 随机访问，但中间插入删除需移动元素。链表通过指针连接节点，定位为 O(n)，已知节点附近插入删除较方便。栈后进先出，可用于函数调用和括号匹配；队列先进先出，可用于任务调度；循环队列用取模复用空间。
## 树与图
二叉搜索树左子树键值小、右子树键值大，平衡时查找约 O(log n)，退化时为 O(n)。堆是完全二叉树，适合优先队列。图由顶点和边组成，广度优先搜索使用队列，适合无权最短路；深度优先搜索使用递归或栈，适合连通性与拓扑相关问题。
## 排序与查找
二分查找要求有序序列，复杂度 O(log n)。插入排序适合小规模或近乎有序数据；归并排序稳定且为 O(n log n)，需额外空间；快速排序平均 O(n log n)，最坏 O(n²)；堆排序最坏 O(n log n) 且原地，但通常不稳定。''',
'操作系统':'''# 操作系统
## 进程与线程
进程是资源分配的基本单位，线程是 CPU 调度的基本单位。同一进程中的线程共享地址空间与打开文件，但拥有各自栈和寄存器上下文。上下文切换需要保存和恢复执行状态。并发表示任务在时间段内交替推进，并行表示同一时刻真正同时执行。
## 调度与同步
先来先服务简单但可能导致护航效应；短作业优先改善平均等待时间但可能饥饿；时间片轮转强调响应；优先级调度需防止低优先级长期等待。互斥锁保护临界区，信号量可表达资源计数和同步顺序。死锁的四个必要条件是互斥、占有且等待、不可剥夺、循环等待。
## 内存管理
分页把虚拟地址空间和物理内存切为固定大小页面与页框，减少外部碎片。缺页时由操作系统调入页面。FIFO 页面置换可能出现 Belady 异常，LRU 利用近期访问历史，时钟算法是近似实现。工作集过大导致频繁换页称为抖动。
## 文件系统
文件系统维护文件、目录、权限和空间分配。绝对路径从根开始，相对路径依赖当前目录。日志文件系统先记录元数据修改意图，异常恢复更可靠。''',
'计算机网络':'''# 计算机网络
## 分层与寻址
TCP/IP 常分为应用层、传输层、网络层和网络接口层。IP 地址定位网络中的接口，MAC 地址用于局域网链路交付。ARP 在 IPv4 局域网中解析 IP 与 MAC 的映射。路由器依据路由表转发数据包，最长前缀匹配选择最具体路由。
## TCP 与 UDP
TCP 面向连接，提供可靠、有序的字节流，并使用序号、确认、重传、流量控制和拥塞控制。三次握手能同步双方初始序号并确认双向通信能力。UDP 无连接、开销小、不保证可靠与顺序，适合实时媒体、DNS 等由应用自行容错的场景。
## HTTP 与 HTTPS
HTTP 是应用层请求响应协议。GET 通常读取资源，POST 通常提交数据。常见状态码：200 成功、301 永久重定向、400 请求错误、401 未认证、403 禁止、404 未找到、500 服务端错误。HTTPS 是 HTTP 运行在 TLS 上，提供传输加密、完整性保护和服务器身份认证。
## DNS 与子网
DNS 把域名解析为地址，解析可能经过浏览器缓存、递归解析器和权威服务器。CIDR 用前缀长度表示网络位，例如 /24。子网掩码与 IP 按位与得到网络地址。''',
'数据库系统':'''# 数据库系统
## 关系模型
关系数据库以表组织数据。主键唯一标识记录且不能重复或为空，外键表达表间引用。实体完整性约束主键，参照完整性约束外键。规范化通过函数依赖减少冗余和更新异常；第三范式通常要求非主属性不传递依赖于候选键。
## SQL
SELECT 查询数据，WHERE 过滤行，GROUP BY 分组，HAVING 过滤分组，ORDER BY 排序。INNER JOIN 只返回匹配行，LEFT JOIN 保留左表全部行。索引以额外空间和写入成本换取查询效率；联合索引通常遵循最左前缀原则。
## 事务
事务具有原子性、一致性、隔离性和持久性，即 ACID。并发异常包括脏读、不可重复读和幻读。隔离级别从低到高通常为读未提交、读已提交、可重复读、串行化。MVCC 通过多版本降低读写冲突，但仍需理解具体数据库实现。
## 查询优化
优化器选择访问路径与连接顺序。应避免无必要的全表扫描，合理设计索引并检查执行计划。索引不是越多越好，低选择性列、频繁更新表和返回大量行的查询需要综合权衡。''',
'Python程序设计':'''# Python 程序设计
## 基础类型
Python 变量保存对象引用。整数、浮点数、字符串和元组通常不可变；列表、字典和集合可变。列表有序且允许重复，元组适合不可变记录，集合适合去重和成员测试，字典以可哈希键映射到值。
## 控制流与函数
if 进行条件分支，for 遍历可迭代对象，while 在条件成立时重复。range 的结束值不包含在序列中。函数参数包括位置参数、关键字参数、默认参数和可变参数。默认可变对象只创建一次，通常应以 None 作为默认值再在函数内初始化。
## 面向对象与异常
类封装状态和行为，实例方法第一个参数通常为 self。继承用于复用与扩展，多态让不同对象响应同一接口。异常应捕获具体类型，finally 无论是否异常都会执行，适合释放资源；with 语句使用上下文管理器确保文件等资源关闭。
## 迭代与工程
迭代器实现逐个取值，生成器使用 yield 惰性产生数据，适合大序列。模块是 Python 文件，包组织模块。虚拟环境隔离依赖，测试应覆盖正常、边界和错误路径。''',
'Java程序设计':'''# Java 程序设计
## 类型与对象
Java 是静态类型语言。基本类型直接保存值，引用类型保存对象引用。类定义字段与方法，对象由 new 创建。封装通过访问修饰符控制可见性；继承表达 is-a 关系；接口定义能力契约，便于多态和解耦。
## 集合
List 有序可重复，Set 通常不重复，Map 保存键值对。ArrayList 随机访问快，中间插入删除可能移动元素；LinkedList 节点操作方便但定位慢；HashMap 平均 O(1) 查找，正确性依赖 equals 与 hashCode 契约。
## 异常与资源
受检异常必须声明或捕获，运行时异常通常表示编程错误或非法状态。try-with-resources 自动关闭实现 AutoCloseable 的资源。finally 适合兜底清理，但不应掩盖原始异常。
## 并发
线程共享堆内存，需要同步保护共享可变状态。synchronized 提供互斥与可见性，volatile 提供可见性和有序性但不保证复合操作原子性。线程池复用线程并限制并发规模，优先使用高级并发工具而非手工管理线程。''',
'C语言程序设计':'''# C 语言程序设计
## 数据与控制
C 是编译型语言，变量类型决定存储大小和解释方式。数组元素连续存放，数组名在多数表达式中退化为首元素指针。字符串以空字符结尾，缓冲区必须预留终止符空间。条件、循环和函数构成结构化程序基础。
## 指针与内存
指针保存地址，解引用访问目标对象。空指针、悬空指针、越界访问和重复释放会导致未定义行为。栈上对象生命周期通常随作用域结束；malloc 在堆上分配，成功后必须配对 free。sizeof 返回对象或类型占用字节数。
## 结构体与文件
结构体组合不同类型字段，可能因对齐产生填充。文件通过 FILE 指针和 fopen 打开，应检查失败并 fclose。文本与二进制模式在部分平台行为不同。头文件放声明，源文件放定义，避免重复定义。
## 编译过程
源代码依次经历预处理、编译、汇编和链接。预处理处理宏与 include；编译生成汇编或目标代码；链接解析跨文件符号。编译警告应认真处理。''',
'软件工程与Git':'''# 软件工程与 Git
## 需求与设计
需求应可验证、无歧义并标明优先级。功能需求描述系统做什么，非功能需求描述性能、安全、可用性等质量属性。模块应高内聚、低耦合，接口明确。架构决策应记录背景、选择与后果。
## 测试
单元测试验证小范围逻辑，集成测试验证模块协作，端到端测试验证用户路径。测试应包含正常、边界、异常与权限场景。回归测试防止修复引入旧问题。自动化测试不能替代代码审查与探索性测试。
## Git
工作区修改通过 git add 进入暂存区，git commit 形成本地提交。分支用于隔离开发，merge 保留合并关系，rebase 重放提交以获得线性历史。远程推送前应拉取并处理冲突，敏感文件不应提交。
## 可维护性
清晰命名、短小职责、必要注释和一致格式降低维护成本。日志应记录可定位的信息而不泄露秘密。发布需具备版本、迁移、回滚与监控策略。''',
'网络与信息安全':'''# 网络与信息安全
## 安全目标
机密性防止未授权读取，完整性防止未授权篡改，可用性保证授权用户可获得服务。身份认证确认是谁，授权决定能做什么，审计记录发生过什么。最小权限和纵深防御是基本原则。
## 密码学基础
对称加密同一密钥加解密，速度快；非对称密码使用公私钥，可用于密钥交换和数字签名。哈希是单向摘要，不是加密。密码应使用带盐、抗暴力的专用算法存储，不能保存明文或简单哈希。
## Web 安全
SQL 注入通过参数化查询防御；跨站脚本通过上下文编码、内容安全策略与安全模板防御；跨站请求伪造通过 SameSite、令牌和来源校验防御。上传文件需限制类型、大小、存储位置与访问权限。
## 运维安全
及时更新补丁，限制公网端口，使用 HTTPS 和强认证。秘密通过环境变量或密钥系统管理，不写入代码和日志。备份必须验证可恢复性，监控应关注异常登录、权限变化和错误率。'''
}
QUESTIONS=[
('计算机组成原理','单选题','简单','计算机中最小的数据单位是什么？',['位','字节','字','块'],'位','位（bit）是最小的数据单位。',['信息表示']),
('计算机组成原理','单选题','中等','缓存能够提高性能主要利用了什么原理？',['局部性原理','摩尔定律','排队论','虚拟化'],'局部性原理','时间局部性和空间局部性使近期或相邻数据更可能再次使用。',['存储层次','局部性']),
('数据结构','单选题','简单','栈的访问顺序是？',['后进先出','先进先出','随机访问','按优先级'],'后进先出','栈遵循 LIFO。',['栈']),
('数据结构','单选题','中等','广度优先搜索通常使用哪种数据结构？',['队列','栈','堆','哈希表'],'队列','BFS 按层扩展，使用队列保存待访问顶点。',['图','BFS']),
('算法','判断题','中等','二分查找可以直接用于任意无序数组。',[],False,'二分查找要求搜索区间有序。',['二分查找']),
('算法','单选题','中等','归并排序的典型时间复杂度是？',['O(n log n)','O(n²)','O(log n)','O(1)'],'O(n log n)','归并排序每层处理 O(n)，共有 O(log n) 层。',['归并排序']),
('操作系统','多选题','中等','死锁的必要条件包括哪些？',['互斥','占有且等待','不可剥夺','循环等待','随机调度'],['互斥','占有且等待','不可剥夺','循环等待'],'四个条件同时成立时才可能死锁。',['死锁']),
('操作系统','判断题','简单','线程是 CPU 调度的基本单位。',[],True,'现代操作系统通常以线程作为调度基本单位。',['进程','线程']),
('计算机网络','单选题','中等','TCP 三次握手的主要目的不包括哪项？',['同步初始序号','确认双向通信','建立连接状态','加密应用数据'],'加密应用数据','加密由 TLS 等协议提供，不是 TCP 握手职责。',['TCP']),
('计算机网络','单选题','简单','DNS 的主要作用是？',['将域名解析为地址','加密网页','分配内存','执行数据库事务'],'将域名解析为地址','DNS 提供名称到地址等记录的解析。',['DNS']),
('数据库','多选题','简单','事务的 ACID 特性包括？',['原子性','一致性','隔离性','持久性','随机性'],['原子性','一致性','隔离性','持久性'],'ACID 对应四项事务性质。',['事务','ACID']),
('数据库','单选题','中等','LEFT JOIN 的特点是？',['保留左表全部行','只保留匹配行','保留右表全部行','自动去重'],'保留左表全部行','左连接保留左表行，右侧无匹配时为 NULL。',['SQL','连接']),
('Python','单选题','简单','Python 中以键值对存储数据的是？',['字典','列表','元组','字符串'],'字典','字典保存键到值的映射。',['字典']),
('Python','判断题','中等','函数的可变默认参数会在每次调用时自动创建新对象。',[],False,'默认参数在函数定义时求值，可变默认对象可能在调用间共享。',['函数','默认参数']),
('Java','单选题','中等','HashMap 正确工作的关键契约涉及哪两个方法？',['equals 与 hashCode','start 与 run','read 与 write','wait 与 sleep'],'equals 与 hashCode','相等对象必须具有相同哈希值。',['集合','HashMap']),
('Java','判断题','中等','volatile 能保证 i++ 操作的原子性。',[],False,'volatile 保证可见性与有序性，但 i++ 是复合操作。',['并发','volatile']),
('C语言','单选题','简单','动态分配的堆内存通常使用哪个函数释放？',['free','close','delete','clear'],'free','malloc/calloc/realloc 获得的内存用 free 释放。',['内存管理']),
('C语言','判断题','中等','所有 C 字符串都应以空字符结尾。',[],True,'C 标准字符串以空字符作为终止标志。',['字符串']),
('软件工程','单选题','简单','用于验证单个函数或类的小范围测试通常称为？',['单元测试','验收测试','压力测试','灰度发布'],'单元测试','单元测试聚焦最小可测试单元。',['测试']),
('Git','单选题','简单','把工作区修改加入暂存区使用？',['git add','git push','git clone','git log'],'git add','git add 更新暂存区。',['Git']),
('信息安全','单选题','中等','防御 SQL 注入最可靠的基础措施是？',['参数化查询','隐藏错误页','压缩响应','增加索引'],'参数化查询','参数与 SQL 结构分离可阻止输入改变语句结构。',['Web安全','SQL注入']),
('信息安全','判断题','简单','哈希与加密完全相同，都能用密钥还原明文。',[],False,'哈希通常是不可逆摘要，不等同于可逆加密。',['密码学'])]

async def main():
    with core.db() as db: users=db.execute("SELECT id,email FROM users WHERE email NOT LIKE '%@example.test' AND email NOT LIKE 'acceptance-%' AND email NOT LIKE 'ui-%'").fetchall()
    output=[]
    for user in users:
        uid,email=user['id'],user['email'];ts=core.now_iso();added_docs=added_q=0
        for name,text in TOPICS.items():
            kbname='计算机知识体系';filename=f'[内置] {name}.md'
            with core.db() as db:
                kb=db.execute('SELECT id FROM knowledge_bases WHERE user_id=? AND name=?',(uid,kbname)).fetchone()
                if not kb:
                    kid=core.uid();db.execute('INSERT INTO knowledge_bases(id,user_id,name,description,created_at,updated_at) VALUES(?,?,?,?,?,?)',(kid,uid,kbname,'系统化计算机科学资料库：本地存储、可检索、可补充。',ts,ts))
                else:kid=kb['id']
                old=db.execute('SELECT id FROM documents WHERE user_id=? AND original_name=?',(uid,filename)).fetchone()
                if old:did=old['id']
                else:
                    did=core.uid();key=f'{uid}_{did}.md';p=Path(core.UPLOAD_DIR)/key;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')
                    db.execute('INSERT INTO documents(id,user_id,original_name,storage_key,mime_type,size_bytes,status,content,summary,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(did,uid,filename,key,'text/markdown',len(text.encode()),'ready',text,f'{name}系统学习资料',ts,ts))
                    db.execute('INSERT INTO document_links(document_id,knowledge_base_id,folder,extraction_method,page_count,index_mode) VALUES(?,?,?,?,?,?)',(did,kid,'内置计算机知识','text',1,'not_indexed'))
                    for c in chunks([Page(1,text,'text')]):db.execute('INSERT INTO document_chunks(id,document_id,user_id,page,ordinal,content) VALUES(?,?,?,?,?,?)',(core.uid(),did,uid,c['page'],c['ordinal'],c['content']))
                    for section in [line[3:] for line in text.splitlines() if line.startswith('## ')]:db.execute('INSERT INTO knowledge_points(id,user_id,title,description,source_document_id,created_at) VALUES(?,?,?,?,?,?)',(core.uid(),uid,section,f'{name}中的核心知识点',did,ts))
                    added_docs+=1
            try:await index_document(did,uid)
            except Exception:
                with core.db() as db:db.execute("UPDATE document_links SET index_mode='keyword',embedding_fingerprint=NULL,error_code=NULL WHERE document_id=?",(did,))
        with core.db() as db:
            for subject,qtype,diff,stem,opts,ans,exp,kps in QUESTIONS:
                if not db.execute('SELECT 1 FROM questions WHERE user_id=? AND stem=?',(uid,stem)).fetchone():
                    db.execute('INSERT INTO questions(id,user_id,subject,type,difficulty,stem,options_json,answer_json,explanation,knowledge_points_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(core.uid(),uid,subject,qtype,diff,stem,json.dumps(opts,ensure_ascii=False),json.dumps(ans,ensure_ascii=False),exp,json.dumps(kps,ensure_ascii=False),ts));added_q+=1
            counts=db.execute("SELECT (SELECT COUNT(*) FROM documents WHERE user_id=? AND original_name LIKE '[内置] %') docs,(SELECT COUNT(*) FROM document_chunks WHERE user_id=?) chunks,(SELECT COUNT(*) FROM knowledge_points WHERE user_id=?) points,(SELECT COUNT(*) FROM questions WHERE user_id=?) questions",(uid,uid,uid,uid)).fetchone()
        output.append({'email':email,'added_documents':added_docs,'added_questions':added_q,**dict(counts)})
    close_clients();print(json.dumps(output,ensure_ascii=False))
if __name__=='__main__':asyncio.run(main())

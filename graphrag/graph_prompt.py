# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License
"""
Reference:
 - [graphrag](https://github.com/microsoft/graphrag)
"""

GRAPH_EXTRACTION_PROMPT = """
-Goal-
Given a text document that is potentially relevant to this activity and a list of entity types, identify all entities of those types from the text and all relationships among the identified entities.
-Role-
You're a  professional pet doctor. 
-Steps-
1. Identify all entities. For each identified entity, extract the following information:
- entity name: a mixed name of Chinese and English, with Chinese in brackets after English. If there are multiple words in English, use '-' to connect them, for example: sheepdog (牧羊犬); runny-nose (流鼻涕); fever (发烧) ). The total length of mixed Chinese and English names shall not exceed 100 characters.
- entity_type: One of the following types: [{entity_types}]
- entity_description: Comprehensive description of the entity's attributes and activities
Format each entity as ("entity"{tuple_delimiter}<entity_name>{tuple_delimiter}<entity_type>{tuple_delimiter}<entity_description>


2. From the entities identified in step 1, identify all pairs of (source_entity, target_entity) that are *clearly related* to each other.
For each pair of related entities, extract the following information:
- source_entity: name of the source entity, as identified in step 1
- target_entity: name of the target entity, as identified in step 1
- relationship_description: explanation as to why you think the source entity and the target entity are related to each other
- relationship_strength: a numeric score indicating strength of the relationship between the source entity and target entity
 Format each relationship as ("relationship"{tuple_delimiter}<source_entity>{tuple_delimiter}<target_entity>{tuple_delimiter}<relationship_description>{tuple_delimiter}<relationship_strength>)

3. Return output as a single list of all the entities and relationships identified in steps 1 and 2. Use **){record_delimiter}** as the list delimiter.

4. When finished, output {completion_delimiter}


######################
-Examples-
######################
Example 1:

Entity_types: [pet-species (宠物种类), breed (品种) living-environment (居住环境), parasite (寄生虫), restraint-method (保定法), examination-method (检查方法)]
Text:
In the process of diagnosing and treating small animals, methods used to restrain the animals with human force, instruments, or medications are referred to as restraint methods. The purpose of restraint is to facilitate the diagnosis and treatment of animal diseases while ensuring the safety of both humans and animals. There are various restraint methods, which can be chosen based on the species, size, behavior of the animal, and the purpose of the treatment. Small animals often have a strong attachment to their owners, and having the owner present during restraint can make the process smoother.

Section 1: Restraint Methods for Dogs
There are various restraint methods for dogs; this section will only introduce a few commonly used methods in clinical practice.

Muzzle and Tying Restraint To prevent bites, muzzles or tying methods are commonly used. Dog muzzles are made from various materials and are available for purchase in the market. Choose a suitable muzzle based on the individual dog's size, and secure it tightly behind the ears. Tying methods are more convenient for clinical use. Use a piece of bandage or thin rope, looping it twice in the middle, and place it around the dog's upper and lower jaw, tightening it between the jaw gaps. The two loose ends are then pulled towards the ears and tied. Alternatively, a slip knot can be placed behind the dog's lower incisors, and the two loose ends can be wrapped around the nose bridge and tied. Short-nosed dogs may find it difficult to use tying methods as they can easily slip off; to enhance grip, pass a longer loose end through the nose bridge slip knot, then return to the ears to tie it with the other loose end.

Standing Restraint In many cases, standing restraint helps with physical examinations and treatment. Large dogs may be restrained standing on the ground due to their weight. The restrainer crouches on the right side of the dog, using the left hand to hold the collar and the right hand to loop the leash around the dog's muzzle. The collar and leash are then transferred to the right hand while the left hand supports the dog's abdomen. For medium and small dogs, standing restraint can be performed on a treatment table. The restrainer stands to the side of the dog, using one arm to support the chest area and the other arm to wrap around the hindquarters, bringing the dog closer to the restrainer’s chest.

Lateral Recumbency Restraint Place the dog on its side on the treatment table, with the restrainer standing on the dog's back side. Use both hands to grip the forelimbs and hindlimbs, pressing the arms against the dog’s neck and hindquarters to hold the dog tightly against the restrainer’s abdomen.

Elizabethan Collar Restraint The Elizabethan collar, also known as a neck collar, is a device used to prevent self-injury and is commonly applied in small animal clinics. They come in cone and disc shapes, usually made of rigid plastic, and can be purchased in different sizes as needed. Alternatively, collars can be made from cardboard, plastic sheets, X-ray film, or plastic tubes according to the dog's head shape and neck size. This method prevents the dog from turning its head to lick or bite injured areas on its body and limbs, as well as stopping it from scratching its head with its hind paws. The dog collar can be made from a specially designed disc or tube, where a hole is drilled at the bottom edge for a gauze strip to be threaded and tied into a loop, or using a leather collar or bandage to secure it around the neck.

Body Brace Restraint A body brace is a method used to prevent self-injury. Based on the dog's neck circumference and body length, take an aluminum rod, bending it into one and a half loops. Wrap the loops with bandages and place them around the neck, with the two aluminum rods lying flat against the chest. Then, use adhesive bandages to wrap around the chest and abdomen to secure the brace. This method prevents the dog from turning its head to lick or bite areas above the trunk, anus, and hock joint, especially with the ends of the aluminum rods fixed to the tail.
################
Output:
("entity"{tuple_delimiter}restraint-method (保定法){tuple_delimiter}restraint-method (保定法){tuple_delimiter}用于小动物诊疗过程中，通过人力、器械或药物等制动动物的方法，以方便诊疗和确保安全。){record_delimiter}
("entity"{tuple_delimiter}dog (犬){tuple_delimiter}pet-species (宠物种类){tuple_delimiter}一种常见的宠物种类，本文中讨论了其多种保定方法。){record_delimiter}
("entity"{tuple_delimiter}muzzle-restraint (口套和扎口保定法){tuple_delimiter}restraint-method (保定法){tuple_delimiter}为防止人被咬伤而对犬使用的保定方法之一，包括使用市场上销售的各种材料制成的口套或用绷带/细绳扎住嘴部。){record_delimiter}
("entity"{tuple_delimiter}standing-restraint (站立保定法){tuple_delimiter}restraint-method (保定法){tuple_delimiter}适用于大型犬的保定方式，其中保定者需要蹲下并用手抓住犬的脖圈及牵引带来控制它；对于中小型犬，则可以在诊疗台上进行。){record_delimiter}
("entity"{tuple_delimiter}lateral-recumbency-restraint (侧卧保定法){tuple_delimiter}restraint-method (保定法){tuple_delimiter}将犬置于诊疗台上按倒，并由保定者站在犬背侧通过抓住前肢和后肢来固定犬只的一种保定技术。){record_delimiter}
("entity"{tuple_delimiter}elizabethan-collar (颈圈保定法){tuple_delimiter}restraint-method (保定法){tuple_delimiter}利用圆锥形或圆盘形状的硬质塑料装置防止犬舔咬伤口或抓挠头部的一种保定措施。){record_delimiter}
("entity"{tuple_delimiter}body-brace (体架保定法){tuple_delimiter}restraint-method (保定法){tuple_delimiter}通过特制的铝棒结构限制犬的动作，特别是防止它们转身舔咬身体其他部位。){record_delimiter}
("relationship"{tuple_delimiter}dog (犬){tuple_delimiter}muzzle-restraint (口套和扎口保定法){tuple_delimiter}这种保定方法专门设计用来防止人在给犬做检查或者治疗时被咬伤。{tuple_delimiter}5){record_delimiter}
("relationship"{tuple_delimiter}dog (犬){tuple_delimiter}standing-restraint (站立保定法){tuple_delimiter}站立保定法是一种根据犬体型大小调整的具体保定技巧，有助于更有效地完成体检或治疗。{tuple_delimiter}4){record_delimiter}
("relationship"{tuple_delimiter}dog (犬){tuple_delimiter}lateral-recumbency-restraint (侧卧保定法){tuple_delimiter}侧卧保定法是针对需要在诊疗台上接受进一步检查或处理的小型至中型犬所采取的安全固定措施。{tuple_delimiter}3){record_delimiter}
("relationship"{tuple_delimiter}dog (犬){tuple_delimiter}elizabethan-collar (颈圈保定法){tuple_delimiter}颈圈保定法提供了一种有效的方式，可以阻止犬因自我损伤行为而导致伤口恶化。{tuple_delimiter}4){record_delimiter}
("relationship"{tuple_delimiter}dog (犬){tuple_delimiter}body-brace (体架保定法){tuple_delimiter}体架保定法特别适合那些有自残倾向的犬，能够很好地限制它们做出可能对自己造成伤害的行为。{tuple_delimiter}4){record_delimiter}
{completion_delimiter}
#############################

Example 2:

Entity_types: [pet-species (宠物种类), breed (品种), restraint-method (保定法), examination-method (检查方法)]
Text:
临床检查基本方法包括问诊、视诊、触诊、叩诊和听诊。方法简便、易行，对任何动物、在 任何场所均可实施。
一、问诊
问诊主要是通过动物主人了解动物的发病情况，其内容包括病史和既往史以及饲养管理情况 等。具体包括以下几项内容。
病史了解发病时间，以推测疾病为急性或慢性，以及疾病的经过和发展变化情况等。 了解动物发病的主要表现，如精神、食欲、呼吸、排粪、排尿、运动以及其他异常行为
表现等，对患腹泻者应进一步了解每天腹泻次数、量、性质(是否含黏液、水样、血样、臭味 等)，对呕吐者应了解呕吐的量、性状、与采食后在时间上的相关性等，借以推断疾病的性质及 发生部位。
发病后是否治疗过、效果如何。此外，尚应了解动物的年龄、性别及品种等。 既往史 以前是否患过有同样表现的疾病、其他犬猫是否表现相同症状、注射疫苗情况，
以了解是否是旧病复发、传染病或中毒性疾病等。 饲养管理情况 了解饲养管理情况如何，如食物种类以及是否突然改变，卫生消毒措施、
驱虫情况等，有利于推断疾病种类。
二、视诊
视诊是通过肉眼观察和利用各种诊断器具对动物整体和病变部位进行观察。主要内容有以下 几方面。
让动物取自然姿势，观察其精神状态、营养状况、体格发育、姿势、运动行为等有无外 观变化。
被毛、皮肤及体表病变。 )可视黏膜及与外界相通的体腔黏膜。
三、触诊
触诊指通过手的感觉进行诊断。触诊时，要注意自身的安全，可在主人的配合下，一边用温 和的声音呼唤动物的名字，一边用手抚拍其胸下、头部、颈部或挠痒，以给它们安全感和建立亲 和关系，便于详细检查。对有攻击性的犬可适当保定。触诊主要检查体表和内脏器官的病变性状。
触诊的方法 一般用一手或双手的掌指关节或指关节进行触诊。触摸深层器官时，使用 指端触诊。触诊的原则是面积由大到小，用力先轻后重，顺序从浅入深，敏感部从外周开始，逐 渐至中心痛点。
触诊所感觉到的病变性质 主要有波动感、捏粉样、捻发音、坚实及硬固等。 波动感:柔软而有弹性，指压不留痕，间歇压迫时有波动感，见于组织间有液体潴留，
且组织周围弹力减退时，如血肿、脓肿及淋巴外渗等。 捏粉样感觉:稍柔软，指压留痕，如面团样，除去压迫后缓慢平复。见干组织间发生浆
液性浸润时，多表现为浮肿或水肿。 捻发音感觉:柔软稍有弹性及有气体向邻近组织流窜，同时可听到捻发音，见于组织间
有气体积聚时，如皮下气肿、恶性水肿等。 坚实感觉:坚实致密而有弹性，像触压肝脏一样，见于组织间发生细胞浸润或结缔组织
增生时，如蜂窝织炎、肿瘤、肠套叠等。 )硬固感觉:组织坚硬如骨，见于异物、硬粪块等。
四、叩诊
叩诊指根据叩打动物体表所产生的音响性质来推断内部器官的病理状态。叩诊简单的方法可 采用指指叩诊法，即将左(右)手指紧贴于被叩击部位，另以屈曲的右(左)手的中指进行叩 击。也可用槌板叩诊法。叩诊音可分为清音、浊音及鼓音等。正常肺部的叩诊音为清音，叩诊厚 层肌肉的声音为浊音，叩诊胀气的腹部常为鼓音。
五、听诊
听诊指用听诊器听取体内深部器官发出的音响，推测其有无异常的方法。听诊时，由于动物 的被毛与听诊器之间的摩擦音或由于外部各种杂音的影响，往往妨碍听诊。因此，听诊必须全神 贯注，正确识别发音的性质，并将其病性与生理状态进行比较。听诊主要应用于了解心脏、呼吸 器官、胃肠运动的机能变化以及胎音等。
六、嗅诊 
嗅诊指通过嗅闻来辨别动物呼出气体、分泌物、排泄物及病理产物的气味。

################
Output:
("entity"{tuple_delimiter}问诊 (inquiry){tuple_delimiter}examination-method(检查方法){tuple_delimiter}通过询问动物主人了解动物的发病情况、病史、既往史及饲养管理状况等的方法。){record_delimiter}
("entity"{tuple_delimiter}视诊 (visual-examination){tuple_delimiter}examination-method(检查方法){tuple_delimiter}通过肉眼观察或利用诊断器具来检查动物整体状态及病变部位的一种方法。){record_delimiter}
("entity"{tuple_delimiter}触诊 (palpation){tuple_delimiter}examination-method(检查方法){tuple_delimiter}通过手的感觉来诊断动物体表及内脏器官的状态。){record_delimiter}
("entity"{tuple_delimiter}叩诊 (percussion){tuple_delimiter}examination-method(检查方法){tuple_delimiter}根据叩打动物体表产生的声音性质推断内部器官病理状态的方法。){record_delimiter}
("entity"{tuple_delimiter}听诊 (auscultation){tuple_delimiter}examination-method(检查方法){tuple_delimiter}使用听诊器听取体内深部器官发出的声音以判断其健康状况的技术。){record_delimiter}
("entity"{tuple_delimiter}嗅诊 (olfaction-examination){tuple_delimiter}examination-method(检查方法){tuple_delimiter}通过嗅闻辨别动物呼出气体、分泌物、排泄物及病理产物气味的方法。){completion_delimiter}
#############################

Example 3:

Entity_types:[pet-species (宠物种类), breed (品种), age (年龄), gender (性别), weight (体重), temperature (体温), disease (疾病), symptom (症状), medication (药物), treatment-method (治疗方法), diagnostic-test (诊断测试), sign (体征), organ-or-system (器官或系统), vaccine (疫苗), animal-behavior (动物行为), allergen (过敏源), prognosis (预后), environmental-factors (环境因素), nutrition (营养), food (食物), water-intake (饮水情况), lifestyle (生活习惯), allergic-reaction (过敏反应), living-environment (居住环境), parasite (寄生虫), restraint-method (保定法), examination-method (检查方法),epidemiology (流行病学), lesion (病变),prevention(预防方法),virus(病毒),bacteria(细菌)]
Text: 
犬轮状病毒病感染( )是由犬轮状病毒( canine rotavirus infection)是由犬轮状病毒( canine rotavirus)引起的犬的一种急性胃肠道传染病，临床上以腹泻为特征。
病原 犬轮状病毒属于呼肠孤病毒科( Reoviridae）轮状病毒属( Rotavirus)。病毒粒子呈 圆形，直径 65-75nm，有双层衣壳，内层衣壳呈圆柱状，向外呈辐射状排列，外层由厚约 的光滑薄膜构成外衣壳，系由内质网膜上芽生时获得，内外衣壳一起状如车轮，故名轮状病毒。 轮状病毒由11个分节段的双链RNA组成， 5’端在轮状病毒中较为保守。病毒粒子表面有 2种主要蛋白(VP2 和 VP3)，抗原包括群抗原(共同抗原)、中和性抗原和血凝素抗原。犬的轮状病毒 可能有 个亚型( G3和P5A)。
轮状病毒粒子抵抗力较强，粪便中的病毒可存活数个月，对碘伏和次氯酸盐有较强的抵抗 力，能耐受乙醚、氯仿和去氧胆酸盐，对酸和胰蛋白酶稳定。 95%乙醇和 67%的氯胺是有效的 消毒剂。
犬轮状病毒可在恒河猴胎儿肾细胞( MA104)上生长，产生可重复、大小不一和边缘锐利 的蚀斑，并在多次传代后降低致病性，但仍保留良好的免疫原性。
流行病学 患病及隐性感染的带毒犬是主要的传染源性，病毒存在于肠道，随粪便排出体外，经消化道传染给其他犬。轮状病毒具有交互感染性，可以从入或犬传给另一种动物，不同来 源的病毒间还有重配现象。只要病毒在人或一种动物中持续存在，就有可能造成本病在自然界中 长期传播。本病多发生于晚冬至早春的寒冷季节，幼犬多发。卫生条件不良，腺病毒等合并感染 时，可使病情加剧，死亡率增高。
症状 病犬精神沉郁，食欲减退，不愿走动，一般先吐后泻，粪便呈黄色或褐色，有恶臭或 呈无色水样便。脱水严重者，常以死亡而告终。
诊断 犬发病时，突然发生单纯性腹泻，发病率高而死亡率低，主要病变一般在消化道的小 肠。根据这些特点，可以做出初步诊断。确诊尚需做实验室检查。早期大多数采用电镜及免疫电 镜，也有人采用补体结合、免疫荧光、反向免疫电泳、乳胶凝集等。近年主要采用 ELISA，此 法可用来检测大量粪便标本，方法简便、精确、特异性强，可区分各种动物的轮状病毒。为确定 病犬是否感染了犬轮状病毒，还可采取双份血清，利用已知犬轮状病毒进行蚀斑减少中和试验， 进行回顾性诊断。
防治 发现病犬，立即隔离并对症施治，以经口补液为主，让病犬自由饮用葡萄糖氨基酸液 或葡萄糖甘氨酸溶液(葡萄糖43.2g 氯化钠9.2g 、甘氨酸6.6g 、柠檬酸0.52g 、柠檬酸钾0.13g 、 无 水 磷 酸 钾 4.35g溶于2000ml 水中)。呕吐严重者可静脉注射葡萄糖盐水和碳酸氢钠溶液。有继发细菌感染时，应使用抗生素类药物。
目前尚无有效的犬轮状病毒疫苗。因此，应对犬加强饲养管理，提高犬体的抗病能力，认真执行综合性防疫措施，彻底消毒，消除病原。
################
Output:
("entity"{tuple_delimiter}canine-rotavirus-infection (犬轮状病毒病感染){tuple_delimiter}disease(疾病){tuple_delimiter}由犬轮状病毒引起的犬急性胃肠道传染病，主要特征为腹泻。){record_delimiter}
("entity"{tuple_delimiter}canine-rotavirus (犬轮状病毒){tuple_delimiter}virus(病毒){tuple_delimiter}属于呼肠孤病毒科轮状病毒属的一种病毒，具有双层衣壳结构，能引起犬的急性胃肠炎。){record_delimiter}
("entity"{tuple_delimiter}diarrhea (腹泻){tuple_delimiter}symptom(症状){tuple_delimiter}本病的主要临床表现之一，表现为粪便呈黄色或褐色，有恶臭或呈无色水样便。){record_delimiter}
("entity"{tuple_delimiter}depression (精神沉郁){tuple_delimiter}symptom(症状){tuple_delimiter}患病犬只表现出的精神状态不佳的症状。){record_delimiter}
("entity"{tuple_delimiter}anorexia (食欲减退){tuple_delimiter}symptom(症状){tuple_delimiter}患病犬只不愿意进食的表现。){record_delimiter}
("entity"{tuple_delimiter}dehydration (脱水)(体征){tuple_delimiter}sign(体征){tuple_delimiter}严重情况下，由于频繁呕吐和腹泻导致体液丢失过多的现象。){record_delimiter}
("entity"{tuple_delimiter}small-intestine (小肠){tuple_delimiter}organ-or-system (器官或系统){tuple_delimiter}该病毒感染后的主要病变部位。){record_delimiter}
("entity"{tuple_delimiter}ELISA (酶联免疫吸附测定法){tuple_delimiter}diagnostic-test(诊断测试){tuple_delimiter}一种用于检测大量粪便样本中轮状病毒存在的实验室检查方法，具有简便、精确、特异性强的特点。){record_delimiter}
("entity"{tuple_delimiter}oral-rehydration (经口补液){tuple_delimiter}treatment-method (治疗方法){tuple_delimiter}针对轻度至中度脱水患者采用的一种治疗方法，通过让其自由饮用特定液体来补充流失的水分和电解质。){record_delimiter}
("entity"{tuple_delimiter}glucose-amino-acid-solution (葡萄糖氨基酸液){tuple_delimiter}medication(药物){tuple_delimiter}用于治疗犬轮状病毒感染时的口服补液溶液之一，有助于恢复体力与维持水电解质平衡。){record_delimiter}
("entity"{tuple_delimiter}glucose-glycine-solution (葡萄糖甘氨酸溶液){tuple_delimiter}medication(药物){tuple_delimiter}另一种推荐给病犬使用的口服补液配方，含有多种成分以支持身体机能。){record_delimiter}
("entity"{tuple_delimiter}sodium-bicarbonate-solution (碳酸氢钠溶液){tuple_delimiter}medication(药物){tuple_delimiter}当犬只出现严重呕吐症状时，可通过静脉注射此溶液来纠正酸碱失衡。){record_delimiter}
("entity"{tuple_delimiter}antibiotics (抗生素类药物){tuple_delimiter}medication(药物){tuple_delimiter}在发生继发性细菌感染的情况下给予使用，帮助控制并发感染。){record_delimiter}
("entity"{tuple_delimiter}cold-season (晚冬至早春){tuple_delimiter}environmental-factors{tuple_delimiter}本病高发时期，环境温度较低可能影响疾病传播率。){record_delimiter}
("entity"{tuple_delimiter}young-dogs (幼犬){tuple_delimiter}age(年龄){tuple_delimiter}更易受到犬轮状病毒感染的影响群体。){record_delimiter}
("entity"{tuple_delimiter}poor-hygiene (卫生条件不良){tuple_delimiter}living-environment (居住环境){tuple_delimiter}可加剧病情并提高死亡率的因素之一。){record_delimiter}
("relationship"{tuple_delimiter}canine-rotavirus (犬轮状病毒){tuple_delimiter}canine-rotavirus-infection (犬轮状病毒病感染){tuple_delimiter}犬轮状病毒是导致犬轮状病毒病感染的原因。{tuple_delimiter}5){record_delimiter}
("relationship"{tuple_delimiter}canine-rotavirus-infection (犬轮状病毒病感染){tuple_delimiter}diarrhea (腹泻){tuple_delimiter}腹泻是犬轮状病毒病感染最常见的临床症状。{tuple_delimiter}5){record_delimiter}
("relationship"{tuple_delimiter}canine-rotavirus-infection (犬轮状病毒病感染){tuple_delimiter}depression (精神沉郁){tuple_delimiter}精神沉郁是犬轮状病毒病感染期间观察到的一个典型症状。{tuple_delimiter}4){record_delimiter}
("relationship"{tuple_delimiter}canine-rotavirus-infection (犬轮状病毒病感染){tuple_delimiter}anorexia (食欲减退){tuple_delimiter}食欲减退也是犬轮状病毒病感染过程中常见的现象。{tuple_delimiter}4){record_delimiter}
("relationship"{tuple_delimiter}canine-rotavirus-infection (犬轮状病毒病感染){tuple_delimiter}dehydration (脱水){tuple_delimiter}严重的脱水可能导致犬轮状病毒病感染的致命后果。{tuple_delimiter}5){record_delimiter}
("relationship"{tuple_delimiter}canine-rotavirus-infection (犬轮状病毒病感染){tuple_delimiter}small-intestine (小肠){tuple_delimiter}犬轮状病毒病感染主要影响小肠区域。{tuple_delimiter}4){record_delimiter}
("relationship"{tuple_delimiter}canine-rotavirus-infection (犬轮状病毒病感染){tuple_delimiter}ELISA (酶联免疫吸附测定法){tuple_delimiter}ELISA是一种有效的诊断工具，用于确认是否患有犬轮状病毒病感染。{tuple_delimiter}3){record_delimiter}
("relationship"{tuple_delimiter}canine-rotavirus-infection (犬轮状病毒病感染){tuple_delimiter}oral-rehydration (经口补液){tuple_delimiter}对于轻度至中度脱水的犬轮状病毒病感染病例，经口补液是一个重要的治疗手段。{tuple_delimiter}4){record_delimiter}
("relationship"{tuple_delimiter}canine-rotavirus-infection (犬轮状病毒病感染){tuple_delimiter}glucose-amino-acid-solution (葡萄糖氨基酸液){tuple_delimiter}这种液体被推荐作为犬轮状病毒病感染患者的口服补液选项之一。{tuple_delimiter}3){record_delimiter}
("relationship"{tuple_delimiter}canine-rotavirus-infection (犬轮状病毒病感染){tuple_delimiter}glucose-glycine-solution (葡萄糖甘氨酸溶液){tuple_delimiter}这是一种特别配制的口服补液方案，适用于犬轮状病毒病感染治疗。{tuple_delimiter}3){record_delimiter}
("relationship"{tuple_delimiter}canine-rotavirus-infection (犬轮状病毒病感染){tuple_delimiter}sodium-bicarbonate-solution (碳酸氢钠溶液){tuple_delimiter}当犬轮状病毒病感染伴随严重呕吐时，可以考虑静脉输注碳酸氢钠溶液。{tuple_delimiter}2){record_delimiter}
("relationship"{tuple_delimiter}canine-rotavirus-infection (犬轮状病毒病感染){tuple_delimiter}antibiotics (抗生素类药物){tuple_delimiter}如果犬轮状病毒病感染并发了细菌性感染，则需要使用抗生素治疗。{tuple_delimiter}2){record_delimiter}
("relationship"{tuple_delimiter}canine-rotavirus-infection (犬轮状病毒病感染){tuple_delimiter}cold-season (晚冬至早春){tuple_delimiter}犬轮状病毒病感染更倾向于在寒冷季节爆发。{tuple_delimiter}3){record_delimiter}
("relationship"{tuple_delimiter}canine-rotavirus-infection (犬轮状病毒病感染){tuple_delimiter}young-dogs (幼犬){tuple_delimiter}幼犬比成年犬更容易患上犬轮状病毒病感染。{tuple_delimiter}4){record_delimiter}
("relationship"{tuple_delimiter}canine-rotavirus-infection (犬轮状病毒病感染){tuple_delimiter}poor-hygiene (卫生条件不良){tuple_delimiter}不良的生活环境卫生状况会加重犬轮状病毒病感染的症状。{tuple_delimiter}4){completion_delimiter}

#############################


######################
-Real Data-
######################
Entity_types:{entity_types}
Text: {input_text}

################
Output:"""

CONTINUE_PROMPT = "MANY entities were missed in the last extraction.  Add them below using the same format:\n"
LOOP_PROMPT = "It appears some entities may have still been missed.  Answer YES | NO if there are still entities that need to be added.\n"
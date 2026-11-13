MASTER = """STEP 1 - paste ONCE at the start of a new ChatGPT chat:
You are my image generator for animated YouTube Shorts. I will send numbered batches of scenes. Rules for EVERY image:
- One separate image per scene, VERTICAL 9:16 portrait (1024x1536), main subject centred, empty space at the top and bottom for captions.
- NO text, letters, numbers, logos or watermarks in the image.
- Keep characters IDENTICAL to the character reference sheet.
- Style: hand-drawn 2D cartoon illustration in a thick-outline doodle-explainer style (same as our Ice Age video): simple characters with round white heads, dot eyes and expressive faces, thin limbs, messy hair; painterly flat colours with soft gradient skies and warm cinematic lighting; richly detailed backgrounds (textures, props, tiny details in every corner); clear foreground / midground / background depth.
- Respectful, reverent, hopeful tone. Never scary. No gore.
- Write the image number before each image (e.g. "Image 003"). Generate all images in the batch without asking questions. When done write "Batch done".

STEP 2 - character reference sheet (generate first, keep it in the chat):
Character reference sheet, hand-drawn 2D cartoon in a thick-outline doodle-explainer style, plain light background, six full-body characters side by side, NO text: (1) [JESUS-STRANGER]: round white head, long brown hair and short beard, kind gentle eyes, dusty patched grey-brown cloak, rope belt, worn sandals, small cloth bundle; (2) [JESUS-REVEALED]: the same face and hair, clean white robe, soft golden glow around him, warm smile; (3) [BOY]: small, round white head, spiky brown hair, blue hoodie; (4) [MOTHER]: round white head, hair in a bun, yellow cardigan, long green skirt; (5) [RICH MAN]: round white head, slicked grey hair, expensive dark suit, scowl; (6) [WORKER]: round white head, short black hair, work apron or uniform. Vertical 9:16.

Per-story helper characters are described inside each prompt; reuse them exactly within a story.
Rules of the story format: Jesus is NAMED in the hook, a poor stranger nobody recognises, one person refuses, a child or a poor person helps, a prayer is answered, his glowing footprints appear, and the last line says they had welcomed their Savior."""
S=[]
def short(id,title,verse,scenes): S.append(dict(id=id,title=title,verse=verse,scenes=scenes))
# scene = (narration, label, prompt)
short(1,"Jesus Came as a Homeless Man, Then a Little Girl Changed Everything","Matthew 25:35-36",[
("Jesus came as a freezing stranger, and nobody knew who he was.","JESUS CAME AS A STRANGER","Snowy city street at dusk, [JESUS-STRANGER] shivering on a bench, snow falling, people hurrying past with scarves, warm shop windows behind, big cold-blue sky"),
("A rich man saw him, and told him to move on.","TOLD HIM TO MOVE","[RICH MAN] pointing angrily down a street at [JESUS-STRANGER] with a wave of his hand, luxury car behind him, snow swirling"),
("Another woman crossed the street to avoid him.","CROSSED THE STREET","A woman in a red scarf crossing to the other side of a snowy street, glancing back uneasily at [JESUS-STRANGER] on the bench, warm streetlights"),
("Then a little girl named Lily stopped.","LILY STOPPED","LILY (small round white head, two braids, red coat, mittens) stopping in the snow and looking at [JESUS-STRANGER], concerned face, soft light"),
("She slipped off her own scarf, and wrapped it around his neck.","HER OWN SCARF","Lily on tiptoes wrapping her red scarf around [JESUS-STRANGER]'s neck, he smiles gently, warm glow between them, snow"),
("Her father stood nearby, ashamed. He had prayed about rent that morning, and nothing had come.","UNANSWERED PRAYER","LILY'S FATHER (round white head, short brown hair, worn jacket) watching, holding an unpaid-rent letter, a faint thought bubble of a prayer, worried, snowy street"),
("But he sat beside the stranger, and shared his last hot soup.","SHARED HIS LAST SOUP","Lily's father sitting on the bench beside [JESUS-STRANGER], pouring hot soup from a thermos into a cup, steam rising, warm light, Lily smiling"),
("The stranger stood, and thanked them, and walked slowly away.","WALKED AWAY","[JESUS-STRANGER] walking away down the snowy street at night, looking back with a gentle smile, lamp light"),
("His footprints began to glow.","FOOTPRINTS GLOWED","Close view of glowing golden footprints in the snow trailing away down the street, sparkles rising, Lily and her father staring in awe"),
("That evening, the landlord called. The rent was forgiven.","RENT FORGIVEN","Lily's father in a small apartment holding a phone to his ear, eyes wide with joy, Lily hugging his leg, warm lamp light, the unpaid-rent letter on the table"),
("They finally understood who he was.","THEY UNDERSTOOD","Lily and her father at the window looking at the glowing footprints fading into the sky, [JESUS-REVEALED] as a bright golden silhouette far off in the snow, tears of joy"),
("They had welcomed their Savior.","WELCOMED THEIR SAVIOR","[JESUS-REVEALED] smiling in a golden glow, hands open, Lily and her father standing before him in warm golden light")])

short(2,"Jesus Came as a Thirsty Traveler, Then a Boy Shared His Last Water","Matthew 25:35",[
("Jesus came as a thirsty traveler, and nobody knew who he was.","JESUS CAME THIRSTY","Hot dusty desert road under a blazing sun, [JESUS-STRANGER] walking slowly with a stick, cracked lips, shimmering heat, small gas station far away"),
("A truck driver sped past, and splashed dust over him.","SPED PAST","Big red truck racing past on the dusty road, dust cloud, [JESUS-STRANGER] shielding his face, harsh sunlight"),
("A shopkeeper said, Water is for customers.","WATER IS FOR CUSTOMERS","[WORKER] shopkeeper in a roadside shop doorway crossing arms and shaking his head, [JESUS-STRANGER] at the counter, shelves of bottled water behind"),
("Then a little boy named Sam saw him.","SAM SAW HIM","SAM (small round white head, spiky brown hair, blue hoodie) standing at the edge of the road holding a half-full water bottle, looking at [JESUS-STRANGER], warm afternoon light"),
("It was his last water, and he was thirsty too.","HIS LAST WATER","Close-up of Sam's hands holding a nearly empty plastic water bottle, his own dry lips, torn expression, hot light"),
("His mother had just prayed for a miracle, because their car had broken down.","BROKEN DOWN","SAM'S MOTHER (round white head, hair in a bun, yellow cardigan) standing next to a broken-down old car with the hood up and steam, hands clasped in prayer, desert road, worried"),
("But Sam walked over, and said, Here, sir, you can have it.","HERE, SIR","Sam handing the water bottle up to [JESUS-STRANGER], who kneels to his height with a gentle smile, warm golden light"),
("The stranger drank, and put a hand on his head, and blessed him.","BLESSED HIM","[JESUS-STRANGER] resting a hand on Sam's head with closed eyes, soft light from above, Sam's mother watching with her hand on her heart"),
("He walked away, and his footprints began to glow.","FOOTPRINTS GLOWED","Glowing golden footprints in the dusty road trailing toward the horizon, sparkles rising, Sam and his mother staring in awe"),
("Their car started, and a tow truck pulled up, free of charge.","IT STARTED","The old car engine running with the hood closed, a tow truck stopping, a friendly driver waving, mother and Sam hugging, bright sunny sky"),
("They finally understood who he was.","THEY UNDERSTOOD","Sam and his mother looking at the glowing footprints, [JESUS-REVEALED] a bright silhouette on the far hill, tears and smiles"),
("They had welcomed their Savior.","WELCOMED THEIR SAVIOR","[JESUS-REVEALED] smiling in a golden glow on the road, hands open, Sam and his mother before him in warm sunset light")])

short(3,"Jesus Came Looking for Work, and Only One Baker Hired Him","Matthew 25:35-40",[
("Jesus came as a poor stranger, looking for work, and nobody knew who he was.","JESUS CAME FOR WORK","Dusty town main street, [JESUS-STRANGER] with a worn bundle knocking at a shop door, shop signs without text, grey sky"),
("A factory boss laughed in his face.","LAUGHED IN HIS FACE","[RICH MAN] in a suit laughing at [JESUS-STRANGER] outside a factory gate, workers watching, smoke from chimneys"),
("A store owner pointed to the door.","POINTED TO THE DOOR","A store owner pointing sternly at the exit, [JESUS-STRANGER] standing humbly in front of a counter, bright shop lights"),
("Then he came to a tiny bakery run by a widow named Ruth.","TINY BAKERY","RUTH (round white head, grey hair in a bun, floury apron) kneading dough in a tiny bakery, glowing oven, three loaves on the shelf, [JESUS-STRANGER] at the door"),
("She had barely enough bread for herself. And she had prayed for a customer that morning.","SHE HAD PRAYED","Ruth looking at an almost empty shelf with three loaves, a faint thought bubble of a prayer, worried, warm oven glow"),
("But she said, Come in. I cannot pay you, but you will not leave hungry.","COME IN","Ruth waving [JESUS-STRANGER] inside with a smile, golden light spilling from the doorway"),
("All day, he carried flour, and fed the oven, and she shared her last loaf.","SHARED HER LAST LOAF","[JESUS-STRANGER] carrying a flour sack while Ruth breaks her last loaf in half and hands him the bigger piece, warm bakery light, flour in sunbeams"),
("At sunset, he thanked her, and walked into the night.","INTO THE NIGHT","[JESUS-STRANGER] walking away down a lantern-lit street at dusk, looking back with a gentle smile"),
("His footprints began to glow.","FOOTPRINTS GLOWED","Glowing golden footprints on the cobblestones outside the bakery, sparkles rising, Ruth at the door staring in awe"),
("By morning, a line of customers stretched down the street, and every shelf was full.","LINE OF CUSTOMERS","Ruth's bakery at dawn, a long line of happy customers outside, shelves overflowing with golden loaves, Ruth crying with joy"),
("She finally understood who he was.","SHE UNDERSTOOD","Ruth at the window looking at faded glowing footprints, [JESUS-REVEALED] a faint golden silhouette far down the street"),
("She had welcomed her Savior.","WELCOMED HER SAVIOR","[JESUS-REVEALED] smiling in a golden glow in the bakery doorway, Ruth kneeling in gratitude in warm morning light")])

short(4,"Jesus Came Sick to the Hospital Door, Then a Nurse Paid His Bill","Matthew 25:36",[
("Jesus came as a sick stranger, and nobody knew who he was.","JESUS CAME SICK","Rainy night outside a hospital entrance, [JESUS-STRANGER] leaning weakly on a wall, coughing into his hand, glowing entrance behind"),
("A receptionist said he could not be treated without money.","NO MONEY","A receptionist behind a glass desk shaking her head, [JESUS-STRANGER] at the counter with empty hands, cold fluorescent light"),
("A doctor walked past, and said, Not my problem.","NOT MY PROBLEM","A doctor in a white coat walking quickly past [JESUS-STRANGER] without looking, clipboard in hand, hallway"),
("Then a young nurse named Hannah saw him.","HANNAH SAW HIM","HANNAH (round white head, dark hair in a ponytail, blue scrubs) stopping in the hospital corridor and looking at [JESUS-STRANGER] with a compassionate face, soft light"),
("She had only enough money for her own mother's medicine. And she had prayed for a miracle.","HER MOTHER'S MEDICINE","Hannah holding a small paper bag of medicine and a few coins, a thought bubble of her sick mother in bed, torn expression, night lamp light"),
("But she took him in, and paid his bill with that money.","PAID HIS BILL","Hannah at the desk handing coins to the receptionist while [JESUS-STRANGER] sits on a chair with a blanket over his shoulders, warm light"),
("She sat beside him all night, and held his hand.","HELD HIS HAND","Hannah holding [JESUS-STRANGER]'s hand by a hospital bed at night, a small lamp glowing, peaceful"),
("At dawn, the bed was empty, and his footprints glowed on the floor.","FOOTPRINTS GLOWED","Empty hospital bed with a folded blanket, glowing golden footprints on the floor leading to the window, morning light, Hannah staring"),
("Her phone rang. Her mother was awake, and the sickness was gone.","HER MOTHER WAS HEALED","Hannah with a phone to her ear, tears of joy, a thought bubble of her mother sitting up in bed smiling, morning sunlight"),
("She finally understood who he was.","SHE UNDERSTOOD","Hannah looking out the window at the sunrise, [JESUS-REVEALED] a bright golden silhouette in the clouds"),
("She had welcomed her Savior.","WELCOMED HER SAVIOR","[JESUS-REVEALED] smiling in warm golden light, hands open, Hannah standing before him with tears of joy")])

short(5,"Jesus Came Lost and Alone, Then a Taxi Driver Stopped","Luke 10:33-35",[
("Jesus came as a lost old man, and nobody knew who he was.","JESUS CAME LOST","Rainy night on a city corner, [JESUS-STRANGER] standing alone with a bundle, headlights blurred, neon glow without text"),
("A bus driver pulled away, just as he reached the stop.","BUS LEFT","A city bus pulling away from a stop in the rain, [JESUS-STRANGER] reaching out a hand, red tail lights"),
("Taxi after taxi drove past, and none would stop.","NONE WOULD STOP","A row of taxis with glowing roof lights passing by on a wet street, [JESUS-STRANGER] small on the sidewalk"),
("Then a tired taxi driver named David slowed down.","DAVID SLOWED DOWN","DAVID (round white head, short black hair, cap, grey jacket) at the wheel of a taxi leaning to look out at [JESUS-STRANGER], tired eyes, warm dashboard glow"),
("He had one fare left, and a daughter who needed a miracle for school.","HIS LAST FARE","David checking the taxi clock and a folded school-fee letter on the dashboard, a thought bubble of his daughter studying, worried"),
("But he opened the door, and said, Get in, I will take you anywhere.","GET IN","David leaning across to open the passenger door of the taxi for [JESUS-STRANGER], warm light spilling out, rain falling"),
("He drove all night, and refused to take a single coin.","NO COIN TAKEN","Inside the taxi, [JESUS-STRANGER] gently holding out a coin, David smiling and pushing it back, city lights glowing outside"),
("At the end, the stranger said, God will not forget this.","GOD WILL NOT FORGET","[JESUS-STRANGER] stepping out of the taxi at dawn on a quiet street, a hand raised in blessing, David smiling inside"),
("His footprints began to glow.","FOOTPRINTS GLOWED","Glowing golden footprints on the wet street trailing away at sunrise, David staring out of his taxi window in awe"),
("That same morning, a scholarship letter arrived for his daughter.","SCHOLARSHIP ARRIVED","David's daughter (small, pigtails) holding up an opened letter with a big smile, David hugging her in a small kitchen, morning light"),
("He finally understood who he was.","HE UNDERSTOOD","David at his taxi looking at fading glowing footprints, [JESUS-REVEALED] a bright golden silhouette in the sunrise"),
("He had welcomed his Savior.","WELCOMED HIS SAVIOR","[JESUS-REVEALED] smiling in a golden glow, hands open, David standing before him in warm sunrise light")])

# ---- Voiceover v2: conversion-focused narration (same scene count/order as the prompts) ----
NEW = {
1:["He was freezing, starving, and everyone walked past him. Nobody knew this was Jesus.",
"A rich man pointed down the street, and said, Move along.",
"A woman crossed the road, so she would not have to look at him.",
"Then a little girl named Lily stopped.",
"She pulled off her own scarf, and wrapped it around his neck.",
"Her father watched, ashamed. That morning, he had prayed about the rent, and heard nothing.",
"But he sat down beside the stranger, and poured out his last hot soup.",
"The stranger smiled, thanked them, and slowly walked away.",
"Then they looked down. His footprints were glowing.",
"That night, the landlord called. The whole rent was forgiven.",
"Lily whispered, Dad... that was Jesus.",
"They had welcomed their Savior. Type Amen if you believe."],
2:["He was dying of thirst, and everyone drove past him. Nobody knew this was Jesus.",
"A truck sped by, and covered him in dust.",
"A shopkeeper told him, Water is only for customers.",
"Then a little boy named Sam stopped.",
"He had one bottle left, and he was thirsty too.",
"His mother stood by their broken-down car, praying for a miracle.",
"Sam looked up at the stranger, and said, Here, sir. You can have it.",
"The stranger drank, placed a hand on his head, and blessed him.",
"Then they looked down. His footprints were glowing.",
"The car started. And a tow truck arrived, for free.",
"His mother whispered, Sam... that was Jesus.",
"They had welcomed their Savior. Type Amen if you believe."],
3:["He begged for work, and every door slammed shut. Nobody knew this was Jesus.",
"A factory boss laughed in his face.",
"A store owner pointed him to the door.",
"Then he found a tiny bakery, run by a widow named Ruth.",
"She had three loaves left, and she had prayed that morning for even one customer.",
"She said, Come in. I cannot pay you, but you will not go hungry.",
"All day he carried flour and fed the oven. And she gave him half of her last loaf.",
"At sunset, he thanked her, and walked into the night.",
"Then she looked down. His footprints were glowing.",
"By morning, the line of customers stretched down the street, and every shelf was full.",
"Ruth whispered... that was Jesus.",
"She had welcomed her Savior. Type Amen if you believe."],
4:["He was sick, and the hospital turned him away. Nobody knew this was Jesus.",
"The receptionist said, No money, no bed.",
"A doctor walked past, and said, Not my problem.",
"Then a young nurse named Hannah stopped.",
"She had just enough money for her own mother's medicine. And she had prayed for a miracle.",
"But she paid his bill with it, and sat beside him all night.",
"She held his hand, until he fell asleep.",
"At dawn, the bed was empty. And his footprints were glowing on the floor.",
"Then her phone rang. Her mother was awake, and completely healed.",
"Hannah whispered... that was Jesus.",
"She had welcomed her Savior. Type Amen if you believe."],
5:["He was lost and alone in the rain, and every taxi drove past. Nobody knew this was Jesus.",
"The last bus pulled away, just as he reached the stop.",
"Taxi after taxi, and none would stop.",
"Then a tired driver named David slowed down.",
"It was his last fare of the night, and his daughter's school fees were due.",
"He opened the door, and said, Get in. I will take you anywhere.",
"He drove all night, and refused to take a single coin.",
"At dawn, the stranger said, God will not forget this.",
"Then David looked down. His footprints were glowing.",
"That very morning, a scholarship letter arrived for his daughter.",
"David whispered... that was Jesus.",
"He had welcomed his Savior. Type Amen if you believe."]}
for s in S:
    assert len(NEW[s['id']])==len(s['scenes']),(s['id'],len(NEW[s['id']]),len(s['scenes']))
    s['scenes']=[(n,l,p) for n,(o,l,p) in zip(NEW[s['id']],s['scenes'])]

# ---- Ink-style rework: Short 1 split into 18 scenes (~2.5 s each) + hook overlay ----
HOOKS={1:"WOULD YOU HAVE HELPED HIM?",2:"WOULD YOU HAVE GIVEN HIM WATER?",3:"WOULD YOU HAVE HIRED HIM?",4:"WOULD YOU HAVE PAID HIS BILL?",5:"WOULD YOU HAVE STOPPED?"}
S[0]['scenes']=[
("He was freezing, starving, and everyone walked past him.","FREEZING & STARVING","Snowy city street at dusk, [JESUS-STRANGER] shivering on a bench with snow on his shoulders, crowds of people in winter coats hurrying past, warm shop windows, cold blue sky"),
("Nobody knew this was Jesus.","NOBODY KNEW","Close portrait of [JESUS-STRANGER] looking up with kind tired eyes, snowflakes on his hair and beard, soft golden halo of lamp light behind his head, blurred crowd"),
("A rich man pointed down the street, and said, Move along.","MOVE ALONG","[RICH MAN] pointing angrily down the street at [JESUS-STRANGER], luxury car behind him, snow swirling"),
("A woman crossed the road, so she would not have to look at him.","CROSSED THE ROAD","A woman in a red scarf crossing to the other side of a snowy street, glancing back uneasily at [JESUS-STRANGER] on the bench, streetlights"),
("Then a little girl named Lily stopped.","LILY STOPPED","LILY (small round white head, two braids, red coat, mittens) stopping in the snow and looking at [JESUS-STRANGER], concerned face, soft light"),
("She pulled off her own scarf, and wrapped it around his neck.","HER OWN SCARF","Lily on tiptoes wrapping her red scarf around [JESUS-STRANGER]'s neck, he smiles gently, warm glow between them, snow"),
("Her father watched, ashamed.","ASHAMED","LILY'S FATHER (round white head, short brown hair, worn jacket) standing a few steps back looking down in shame, hands in pockets, snowy street"),
("That morning, he had prayed about the rent, and heard nothing.","UNANSWERED PRAYER","Lily's father holding an unpaid-rent letter, a faint thought bubble of him praying with folded hands, worried, snow falling, warm window light behind"),
("But he sat down beside the stranger.","SAT BESIDE HIM","Lily's father sitting down on the bench beside [JESUS-STRANGER], Lily smiling in front of them, warm lamp light"),
("And poured out his last hot soup.","HIS LAST SOUP","Close-up of Lily's father pouring hot soup from a thermos into a cup, steam rising, held out to [JESUS-STRANGER]'s hands, warm glow"),
("The stranger smiled, and thanked them.","THANK YOU","[JESUS-STRANGER] smiling gently with the steaming cup in both hands, Lily and her father beside him, warm golden light"),
("Then he slowly walked away.","WALKED AWAY","[JESUS-STRANGER] walking away down the snowy street at night, looking back with a gentle smile, lamp light, long shadow"),
("They looked down. His footprints were glowing.","FOOTPRINTS GLOWED","Close view of glowing golden footprints in the snow trailing away down the street, sparkles rising, Lily and her father staring in awe"),
("That night, the landlord called.","THE LANDLORD CALLED","Lily's father in a small apartment holding a phone to his ear, wide-eyed, Lily at his side, warm lamp light"),
("The whole rent was forgiven.","RENT FORGIVEN","Lily's father crying and laughing with the phone lowered, hugging Lily, the unpaid-rent letter on the table now glowing softly, warm golden room"),
("Lily whispered, Dad... that was Jesus.","THAT WAS JESUS","Lily and her father at the window looking out at the glowing footprints fading in the snow, [JESUS-REVEALED] a faint bright golden silhouette far down the street"),
("They had welcomed their Savior.","WELCOMED THEIR SAVIOR","[JESUS-REVEALED] smiling in a golden glow, hands open, Lily and her father standing before him in warm golden light"),
("Type Amen if you believe.","TYPE AMEN","Warm golden sunrise over a snowy city rooftop, a soft glowing heart of light in the sky, tiny silhouettes of a girl and her father waving, hopeful"),
]

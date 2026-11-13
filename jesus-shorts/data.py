MASTER = """STYLE LOCK (paste first in ChatGPT, then send each prompt):
Photorealistic cinematic documentary photograph, shot on a 35mm lens, natural soft daylight or warm street light, shallow depth of field, candid real-life look, realistic skin and clothing texture, modern everyday setting. VERTICAL 9:16 portrait, main subject in the centre, clear space at top and bottom for captions. NO text, NO letters, NO logos, NO watermark, no cartoon or painting look. Respectful, emotional, hopeful tone.
RECURRING CHARACTER [STRANGER]: a thin tired man in his 30s-40s, shoulder-length brown hair, short beard, kind deep brown eyes, worn grey-brown coat with patches, old scarf, carries a small cloth bundle. Looks poor and helpless but his eyes are calm and gentle.
REVEAL: the same man shown only as a warm glowing silhouette or from behind in golden light, never frightening, never a face close-up. Keep the same face and build whenever he appears.
Keep each story's other characters identical across all of its images (same face, clothes, ages)."""
S = []
def short(id,title,verse,scenes): S.append(dict(id=id,title=title,verse=verse,scenes=scenes))

short(1,"Child Gave His Lunch to a Helpless Man, Then God Rewarded Him","Matthew 25:35-40",[
("Everyone walked past this starving man. Except one boy.","Busy city sidewalk, crowd walking past, [STRANGER] sitting weak against a wall, a young boy NOAH (8, blue hoodie) stopping to look at him"),
("The man had not eaten in three days.","Close portrait of [STRANGER] sitting on cold pavement, hollow cheeks, tired eyes, hand on stomach"),
("People looked away, and some even laughed.","Passers-by in business clothes walking past [STRANGER], one woman pulling her child's hand away"),
("But Noah, just eight years old, saw him.","Noah standing still in the crowd, looking at [STRANGER] with concern, soft focus background"),
("He had only one sandwich, and it was his lunch.","Close on Noah's small hands holding a wrapped sandwich in a brown paper bag, school backpack on his shoulder"),
("His stomach was growling too.","Noah touching his own stomach, hesitating, looking down at the sandwich"),
("But he walked over, and said, Sir, please, take this.","Noah holding out the sandwich to [STRANGER], who looks up in surprise, eye-level shot"),
("The man cried. No one had been kind to him in years.","[STRANGER] taking the sandwich with both hands, tears in his eyes, Noah smiling"),
("The man blessed him, and said, You will never go hungry.","[STRANGER] resting a gentle hand on Noah's shoulder, warm light between them"),
("Noah walked home with an empty bag.","Noah walking along a quiet suburban street at sunset, empty paper bag in hand, long warm shadows"),
("But at home, his mother had a surprise.","Noah opening the door of a small home, his mother hands to her mouth in joy, kitchen light"),
("Her prayer for work was answered that same day, and the table was full.","Small family table full of food, mother crying and laughing with Noah, warm golden window light"),
("Whatever you do for the least of these, you do for Me.","Glowing silhouette of a long-haired bearded man standing at the end of the street in golden light, Noah's family on the porch looking")])

short(2,"Poor Waitress Fed a Homeless Man, Then God Rewarded Her","Matthew 25:35",[
("She had nine dollars, and he had nothing.","Night diner interior, young waitress GRACE (late 20s, ponytail, apron) wiping a counter, rain on the window, [STRANGER] outside looking in"),
("He stood in the rain, looking through the window.","[STRANGER] soaked outside a diner window in rainy night, face lit by neon glow, hands in coat"),
("Her manager said, Do not let him in.","Angry manager in a white shirt pointing at the door, Grace uneasy behind the counter, tense mood"),
("But Grace saw how cold he was.","Close on Grace's compassionate eyes looking toward the window, warm diner light on her face"),
("She slipped out the back and brought him inside.","Grace holding the door open to [STRANGER] on a rainy night, steam and warm light spilling out"),
("She paid for his soup with her last nine dollars.","Grace handing coins and notes across the counter, a steaming bowl of soup on a tray, quiet moment"),
("He ate slowly, with shaking hands.","Close on [STRANGER]'s trembling hands around a hot soup bowl, steam rising, warm light"),
("The manager fired her on the spot.","Manager angrily taking Grace's apron, Grace stunned, [STRANGER] watching sadly"),
("Grace walked out into the rain with nothing.","Grace walking alone down a wet street at night, apron folded in her hand, city lights blurred"),
("But the stranger was gone, and a car pulled up.","Rainy street, empty bench where [STRANGER] sat, a car stopping in the foreground with headlights glowing"),
("The owner had watched everything. He gave her a better job that very night.","Elegant older man in a coat shaking Grace's hand outside the diner, Grace stunned and tearful, warm streetlight"),
("Kindness is never wasted.","Glowing silhouette of a long-haired bearded man walking away down the rainy street into golden light")])

short(3,"Truck Driver Stopped for an Old Man, Then God Rewarded Him","Luke 10:36-37",[
("Thousands drove past. Only one man stopped.","Wet rural highway at dusk, cars rushing by, [STRANGER] standing by a broken-down old car with the hood up, waving weakly"),
("His car had died on a cold, empty road.","[STRANGER] leaning on his dead car in the cold dusk, breath visible, hands on the hood"),
("Car after car sped away.","Long exposure of headlights streaming past on the dark highway, [STRANGER] small by the roadside"),
("Then a tired truck driver named Daniel saw him.","DANIEL (50s, flannel jacket, cap) at the wheel of a big truck looking at the road ahead, sunset glow in the cabin"),
("Daniel was already late for his delivery.","Daniel's face lit by the dashboard clock reading late, torn expression"),
("But he pulled over anyway.","Large truck pulling onto the shoulder with hazard lights flashing in the dusk"),
("He towed the car, and gave the man his coffee.","Daniel hooking a tow strap to [STRANGER]'s car, a thermos of coffee handed over, warm headlight glow"),
("The stranger said, God will not forget this.","[STRANGER] smiling gently at Daniel, hand on his arm, golden low light"),
("Daniel got fired the next morning for being late.","Daniel in an office doorway holding a cardboard box, supervisor in a suit shaking his head, grey light"),
("But then his phone rang.","Daniel sitting in his parked truck at dawn looking at his phone with surprise, soft morning light"),
("A company owner offered him a better job, with higher pay.","Daniel shaking hands with a smiling business owner in front of a modern logistics warehouse, golden morning"),
("God sees every act of kindness.","Glowing silhouette of a bearded man standing on the highway horizon in golden sunrise light")])

short(4,"Girl Shared Her Last Bread With a Beggar, Then God Rewarded Her","Matthew 25:40",[
("She had one slice of bread, and a stranger was starving.","Dim village market alley, girl MIA (10, braided hair, worn yellow coat) holding a slice of bread, [STRANGER] sitting in a doorway"),
("Mia lived with her grandmother, and they had almost nothing.","Small tidy poor kitchen, grandmother and Mia at a table with a single slice of bread, soft window light"),
("On the way home, she saw a man shaking in a doorway.","Mia walking home at dusk, stopping, looking at [STRANGER] shivering in a stone doorway"),
("His lips were blue from the cold.","Close portrait of [STRANGER] with pale blue-tinted lips, frost on his scarf, tired eyes"),
("She knew her grandmother needed this bread.","Mia gripping the bread tightly with both hands, torn expression, soft focus street behind"),
("But she remembered what her grandmother taught her.","Mia in warm flashback glow, grandmother's hands folded in prayer behind a soft vignette"),
("She broke the bread in half, and gave him the bigger piece.","Mia handing the larger half of the bread to [STRANGER], their hands almost touching, warm light"),
("He smiled, and said, Go home, little one. Look at your door.","[STRANGER] gently pointing past Mia toward her house down the alley, warm light on his face"),
("At home, the door was covered with bags of food.","Mia's grandmother opening a wooden door, grocery bags and boxes piled on the step, both stunned"),
("Neighbours were cooking and laughing in their kitchen.","Mia and her grandmother at a table with neighbours bringing steaming dishes, warm kitchen light, tears of joy"),
("No one knew who had sent them.","Mia looking out the window at the empty alley where [STRANGER] was, a faint golden glow in the street"),
("Give, and it shall be given to you.","Glowing silhouette of a bearded long-haired man at the far end of the alley in warm golden light")])

short(5,"Cleaner Gave His Only Coat to a Freezing Man, Then God Rewarded Him","Matthew 25:36",[
("It was the coldest night of the year. One man had a coat.","Snowy city night, [STRANGER] sitting against a church door, lamp light, falling snow, breath clouds"),
("A freezing man sat outside the church.","[STRANGER] hugging his knees on the cold stone steps, snow on his shoulders, frost on his beard"),
("Rich people in warm clothes walked right past.","Well-dressed churchgoers in long coats and scarves walking past [STRANGER] without looking, snow falling"),
("Only the old cleaner, Samuel, stayed behind.","SAMUEL (60s, grey beard, dark work jacket, keys on a ring) locking a church door at night, tired kind face"),
("He had one coat, and a sick daughter at home.","Samuel looking at his thin worn coat, a faint thought glow of a sick girl in bed at home"),
("He looked at the freezing man, and his heart broke.","Close on Samuel's compassionate eyes in the snowfall, lamp light on his face"),
("He took off his only coat, and put it around his shoulders.","Samuel draping his coat over [STRANGER] on the steps, snow falling, tender warm rim light"),
("He sat beside him, and shared his last bread.","Samuel and [STRANGER] sitting side by side on the church steps sharing bread, quiet bond, snow"),
("Samuel walked home in the freezing night, shaking.","Samuel walking alone in the snowy street in just a thin sweater, hunched against the cold, lamp-lit"),
("When he opened the door, his daughter was sitting up.","Samuel opening the door of a small home, a young girl sitting up in bed with a big smile, warm lamp light"),
("She was healed. And on the table lay his coat, warm and glowing.","Father and daughter hugging, Samuel's coat folded glowing gently on the table behind them, warm golden room"),
("When you clothe the cold, you clothe Him.","Glowing silhouette of a long-haired bearded man at the door in golden light, snowflakes turning to sparkles")])

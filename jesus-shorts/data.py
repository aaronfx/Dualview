# Each short: dict(id,title,verse,scenes=[(narration,prompt)])  -- vertical 2:3 portrait compositions
MASTER = """STYLE LOCK (paste first in ChatGPT, then send each prompt):
Richly painted, detailed storybook illustration in a warm cinematic style, first-century Galilee/Judea setting (stone houses, clay roofs, olive trees, linen and wool clothing, oil lamps). VERTICAL portrait 2:3 composition, subject in the centre third, empty space at top and bottom for captions. Soft golden-hour or lamp light, expressive faces, fine painted texture, NO text, NO letters, NO watermark. Respectful, reverent tone; no gore.
RECURRING CHARACTER [JESUS-DISGUISED]: a thin tired stranger in his early 30s, shoulder-length brown hair, short beard, kind deep brown eyes, dusty patched grey-brown tunic, frayed rope belt, worn sandals, a small bundle on a stick. Looks poor but his eyes are gentle and steady.
[JESUS-REVEALED]: same face, now in a clean white robe with a soft golden light around him, warm loving smile; the dusty clothes are gone. Calm, never scary.
Always keep the same face for both."""
S = []
def short(id,title,verse,scenes): S.append(dict(id=id,title=title,verse=verse,scenes=scenes))

short(1,"He Asked for Work. Nobody Hired Him.","Matthew 25:35-40",[
("Nobody wanted to hire the stranger.","Wide dusty village street at midday, [JESUS-DISGUISED] knocking at a closed wooden workshop door, merchants turning their backs, heat haze"),
("He was thin, tired, and covered in dust.","Close portrait of [JESUS-DISGUISED], dust on his cheeks, tired kind eyes, sunlit stone wall behind him"),
("Door after door closed in his face.","A row of three closed doors in a stone alley, a hand pushing one shut, [JESUS-DISGUISED] standing small in front"),
("Then he came to a small bakery, run by a widow named Ruth.","Small stone bakery with a glowing clay oven and a few loaves on a wooden shelf, RUTH, a worn kind widow in a headscarf, kneading dough"),
("He asked, Please, I only need work for a day.","[JESUS-DISGUISED] at the bakery door, hands open and humble, Ruth looking up from her dough"),
("Ruth had barely enough bread for herself.","Close shot of an almost empty shelf with three loaves, Ruth counting them with worry, warm oven glow"),
("Still, she said, Come in. I cannot pay much, but you will not leave hungry.","Ruth waving [JESUS-DISGUISED] in with a gentle smile, golden light spilling from the doorway"),
("All day he carried flour and fired the oven.","[JESUS-DISGUISED] carrying a heavy sack of flour across the bakery, flour dust in sunbeams, Ruth smiling behind"),
("At sunset, she gave him half of her last loaf.","Ruth handing [JESUS-DISGUISED] half a loaf of bread on a cloth, sunset through the window, tender moment"),
("He thanked her, and walked into the night.","[JESUS-DISGUISED] walking away down a lantern-lit stone street at dusk, bundle on his shoulder, glancing back softly"),
("The next morning, her shelves were overflowing.","Ruth in shock in the bakery at dawn, every shelf piled with golden loaves, light streaming, hands to her mouth"),
("On the table lay a note, I was a stranger, and you took me in.","A folded parchment on the wooden table glowing gently, [JESUS-REVEALED] faintly visible as a bright silhouette in the doorway, golden light"),
("Whoever helps the least of these, helps Him.","[JESUS-REVEALED] smiling warmly with hands open, golden glow, Ruth kneeling in gratitude in front of him")])

short(2,"A Beggar Knocked in the Storm","Hebrews 13:2",[
("A terrible storm hit the village.","Night storm over a hillside village, lightning, bending olive trees, rain sheets, small lit windows"),
("At the edge of town, a beggar was shaking in the cold.","[JESUS-DISGUISED] soaked, shivering against a stone wall in the rain, hugging himself, lightning flash behind"),
("He knocked on the rich man's door.","Huge ornate wooden door of a rich house, [JESUS-DISGUISED] knocking small and cold, warm light under the door"),
("The rich man shouted, Go away.","A rich man in fine robes at the door with an angry waving hand, [JESUS-DISGUISED] stepping back, rain"),
("He knocked on three more doors. No one answered.","Three dark closed doors in a rainy lane, [JESUS-DISGUISED] walking between them, head bowed"),
("At the very last house, lived a poor shepherd and his small son.","Tiny stone hut with one glowing window at the village edge, a shepherd and his boy TOBIAS visible inside by lamp"),
("The shepherd opened the door and said, We have little. But come in.","The shepherd opening the door, boy peeking behind his leg, [JESUS-DISGUISED] dripping at the threshold, warm light"),
("They shared their soup, and the stranger's shaking stopped.","Interior: three at a small table sharing a bowl of soup, oil lamp glow, [JESUS-DISGUISED] smiling for the first time, boy giggling"),
("He slept by the fire, and they gave him their only blanket.","The shepherd laying a wool blanket over sleeping [JESUS-DISGUISED] by the hearth, the boy watching sleepily"),
("At dawn, the stranger was gone.","Empty hearth with the folded blanket, sunrise through the door, the shepherd puzzled, boy pointing outside"),
("Outside, their dry field had become green and full of sheep.","Shepherd and boy at the doorway seeing a lush green hillside with many sheep, golden sunrise, rainbow"),
("Some have shown kindness to angels without knowing it.","[JESUS-REVEALED] standing on the hill in golden light, gentle smile, sheep around him, blessing hand raised")])

short(3,"The Boy Who Gave His Last Fish","Matthew 25:40",[
("A poor boy sold fish at the market.","Busy ancient market square at morning, a small boy JONAH behind a basket with a few fish, stalls and colour"),
("He needed one more sale to feed his family.","Close on the boy's worried face counting two small coins, a basket with only one fish left"),
("A hungry stranger approached him.","[JESUS-DISGUISED] stepping up to the boy's stall, tired, one hand on his stomach, market blur behind"),
("The stranger had no money. Only an empty hand.","Close on [JESUS-DISGUISED]'s open empty palm held out gently, warm afternoon light"),
("Everyone else laughed and walked on.","Market crowd laughing and walking past [JESUS-DISGUISED], a woman pulling her child away, painted motion"),
("The boy looked at his last fish. And thought of his own hunger.","The boy holding his last fish up in both hands, torn expression, soft light on his face"),
("Then he wrapped it in a cloth, and gave it away.","The boy placing the wrapped fish into [JESUS-DISGUISED]'s hands, small smile, golden light between them"),
("The stranger blessed him, and slowly disappeared into the crowd.","[JESUS-DISGUISED] resting a gentle hand on the boy's head, crowd soft in the background"),
("That evening, the boy walked home with an empty basket.","The boy walking home on a sunset path with an empty basket, calm and quiet, long shadows"),
("But his father was waiting at the shore, with a miracle.","The boy's father pointing at a fishing boat on the sea at sunset, boat sinking low with silver fish"),
("Their nets were so full, they could barely pull them in.","Father and boy hauling a huge net overflowing with silver fish, golden water splashing, joy"),
("What you give to the least, you give to Jesus.","[JESUS-REVEALED] standing on the shore in the golden light, warm smile, boy's silhouette looking up")])

short(4,"Two Men Passed. One Stopped.","Luke 10:36-37",[
("A cart broke down on a lonely road.","Long dusty road through hills at noon, a wooden cart with a broken wheel, [JESUS-DISGUISED] kneeling beside it, tired"),
("The stranger could not move it alone.","[JESUS-DISGUISED] straining to lift the heavy cart, sweat on his forehead, heat shimmer"),
("A rich merchant rode by on a fine horse.","A rich merchant on a white horse with a jewelled saddle riding past, looking away, dust cloud"),
("He did not even slow down.","Close on the merchant's cold eyes turning from the stranger, horse hoofs lifting dust"),
("Then a poor farmer named Daniel came by, carrying his tools.","DANIEL, a weathered kind farmer with a hoe on his shoulder walking along the road, bag of seeds, tired but warm"),
("He was late for his own field, but he stopped anyway.","Daniel pausing on the road, looking back at the stranger, hesitation then resolve, soft light"),
("Together, they lifted the cart and fixed the wheel.","Daniel and [JESUS-DISGUISED] pushing a wooden wheel into place with ropes and a wedge, teamwork, golden dust"),
("The stranger thanked him, and said, Your field will be blessed.","[JESUS-DISGUISED] gripping Daniel's forearm in thanks, gentle smile, hills behind"),
("Daniel hurried to his dry, cracked ground.","Cracked parched farmland under a hard sun, Daniel standing over it, hoe in hand, worried"),
("Then the clouds gathered, and rain began to fall.","Dark clouds opening over the field, rain falling on Daniel's upturned face, joyful tears, light breaking through"),
("By harvest, his barns were the fullest in the valley.","Overflowing barn of golden wheat, Daniel and his family laughing in the harvest light"),
("Who is my neighbour? The one who stopped.","[JESUS-REVEALED] on the hill smiling at the field, golden light, hand raised in blessing")])

short(5,"The Man at the Temple Door","Matthew 25:36",[
("It was the coldest night of the year.","Snowy-looking cold night in an old stone town, frost on cobblestones, lamplight, breath clouds"),
("A shivering man sat outside the temple doors.","[JESUS-DISGUISED] sitting against huge temple doors in the cold, hugging his knees, snow dusting his shoulders"),
("People in fine clothes walked right past him.","Wealthy worshippers in fur-trimmed robes walking past [JESUS-DISGUISED] without looking, heads high"),
("Only the old cleaner stayed behind to lock up.","SAMUEL, an elderly humble cleaner with a broom and ring of keys at the temple door, tired kind face"),
("Samuel had only one coat. And his daughter was sick at home.","Samuel looking at his single worn coat, thought bubble of a sick girl in bed at home, warm lamp"),
("Still, he looked at the stranger, and his heart broke.","Close on Samuel's compassionate eyes looking at [JESUS-DISGUISED], light on his face"),
("He took off his coat, and placed it on the stranger's shoulders.","Samuel draping his coat around [JESUS-DISGUISED], breath clouds, tender, warm golden rim light"),
("Then he shared his bread, and sat with him a while.","Samuel and [JESUS-DISGUISED] sharing a piece of bread on the temple steps under a lamp, quiet connection"),
("When he got home, he found a miracle.","Samuel opening the door of his small home, light spilling out, surprised expression"),
("His daughter was sitting up, healed, smiling.","A young girl sitting up in bed, cheeks glowing with health, laughing, Samuel's tears of joy, warm lamp"),
("On the table lay his coat. It was warm and glowing.","Samuel's coat folded on the table glowing gently, a soft golden light from the doorway where [JESUS-REVEALED] fades into the night"),
("When you clothe the cold, you clothe Him.","[JESUS-REVEALED] smiling in a gentle golden glow, snowflakes turning to light around him")])

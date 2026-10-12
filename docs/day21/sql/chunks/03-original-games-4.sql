-- 块 4（9 条）
INSERT INTO original_games (id, th, title, subtitle, category, year, cover, tag) VALUES
('th175', 'Th17.5', '东方刚欲异闻', 'Suibotsushita', 'spin', '2021', 'assets/covers/th175.jpg', '刚欲异闻'),
('manga01', '漫画', '东方三月精 ~ Eastern and Little Nature Deity.', '作画：比良坂真琴 · 全1卷', 'manga', '2005–2007', 'assets/covers/manga01.jpg', '三月精'),
('manga02', '漫画', '东方三月精 ~ Strange and Bright Nature Deity.', '作画：比良坂真琴 · 全3卷', 'manga', '2006–2009', 'assets/covers/manga02.jpg', '三月精'),
('manga03', '漫画', '东方三月精 ~ Oriental Sacred Place.', '作画：比良坂真琴 · 全3卷', 'manga', '2009–2012', 'assets/covers/manga03.jpg', '三月精'),
('manga04', '漫画', '东方三月精 ~ Visionary Fairies in Shrine.', '作画：比良坂真琴 · 全3卷', 'manga', '2016–2019', 'assets/covers/manga04.jpg', '三月精'),
('manga05', '漫画', '东方儚月抄 ~ Silent Sinner in Blue.', '作画：秋★枝 · 全3卷', 'manga', '2007–2009', 'assets/covers/manga05.jpg', '儚月抄'),
('manga06', '漫画', '东方儚月抄 ~ 月宫的兔子与地上的兔子', '作画：あらたとしひら · 全2卷', 'manga', '2007–2009', 'assets/covers/manga06.jpg', '儚月抄'),
('manga07', '漫画', '东方茨歌仙 ~ Wild and Horned Hermit.', '作画：あずまあや · 全10卷', 'manga', '2010–2019', 'assets/covers/manga07.jpg', '茨歌仙'),
('manga08', '漫画', '东方铃奈庵 ~ Forbidden Scrollery.', '作画：春河もえ · 全7卷', 'manga', '2012–2017', 'assets/covers/manga08.jpg', '铃奈庵')
ON CONFLICT (id) DO NOTHING;

## Description

👉 Check our documentary "Beyond The Success Of Kotlin: https://youtu.be/E8CtE7qTb-Q
👉 Integrate GitHub Copilot and ChatGPT into your daily work for streamlined, efficient development.
https://aw.club/global/en/courses/ai-supported-software-engineering

Leverage generative AI to minimize repetitive efforts throughout the software testing lifecycle.
https://aw.club/global/en/courses/ai-supported-testing
We are launching a new original series on the Anywhere Club YouTube channel, where we will share insightful and inspiring stories about technologies and people behind them. 

Our first episode is simple but substantial — top-notch software engineers will share their best advice on becoming exceptional developers. 

🔹 Andrey Breslav - ex-Kotlin Lead Language Designer
🔹 Dmitry Jemerov - co-author of "Kotlin in Action"
🔹 Egor Tolstoy - Kotlin Project Lead / JetBrains
🔹 Pavel Veller - Chief Technologist / EPAM Systems
🔹 Roman Elizarov - ex-Kotlin Project Lead

We hope you enjoy this video and stay tuned for more!

ANYWHERE CLUB ON THE INTERNET
🔸 Web: https://bit.ly/awclub-en
🔸 Discord: https://epa.ms/acd
🔸 Instagram: https://instagram.com/anywhere_club

#awclub #tech #engineering

## Transcription

### Intro

[Music] The topmost advice, I learned. That was predictable. Being a good developer—that's a very loaded question. It starts with the definition of good. Being a good programmer takes several qualities. First of all, there's attention to detail. Programming is all about small details. Things that in casual communication or text wouldn't matter—a missing comma or flipped word. But in programming, just one character out of place or an off-by-one error somewhere can be the difference between code that works and code that doesn't. Attention to small details is what makes professional developers different. That's the quality needed to become a good software developer. [[00:00:13]](https://youtube.com/watch?v=suATPK45sjk_transcript&t=13s)

### What makes a good developer

I enjoy working with extremely good and very junior developers. They arguably know little, but the way they approach tasks, the way they learn and their curiosity and hunger to do things—it's an amazing experience. They're great developers; they're just great junior developers. So first, the greatness in this question doesn't equate with experience necessarily, especially years of experience. My first point is fundamentals. If you're using a data structure—a library, list, or map—do you know how it works? What algorithms are implemented? Why is it fast? Do you know how memory is managed in the runtime you're using? What happens under the hood to manage concurrency, like synchronized threads? Understanding how things work under the hood makes you a better engineer. You learn from engineering decisions made by others. It exercises your mind analytically in ways you need for your own code. It also makes you knowledgeable—much easier to figure things out and make connections that aren't obvious. [[00:01:37]](https://youtube.com/watch?v=suATPK45sjk_transcript&t=97s)

### Fundamentals

I remember being interviewed by a startup CTO some twelve years ago. He asked a question I then kept asking in my own interviews. It's simple: for web developers, imagine a button on a webpage. You click it, and the next page comes. What happened between the button click and the next page? Think about it. That onion can have five layers or a thousand. You can spend five minutes answering or an hour without being halfway through, depending on how many things happen or can happen. The more layers of that onion you can knowingly discuss, the better you understand the system and the better web developer you'll be. Things like network protocols, database architecture—with so much software being open source today, you can look under the hood of almost any technology you use. You should do that. Read books and watch presentations about how different software works. The main benefit is that it helps you resolve problems much more confidently and quickly than just poking at things and trying different approaches. [[00:03:13]](https://youtube.com/watch?v=suATPK45sjk_transcript&t=193s)

### Identity

Don't tie your identity to a specific technology or set of practices. I see a lot of people saying they're a Kotlin developer or a Python developer or an Android developer. People who say that sometimes view others who aren't as not like them—maybe as competitors or enemies. Or they think those people are stupid and don't know what they're doing, and that they should be using the best language on the planet, which is Kotlin. I don't think this is healthy. It's much better to identify yourself as a developer and learn what tools exist, what tools can benefit you in which cases, and use the best tool for the job. Base your identity on something else. During your career, you will have to learn many different languages, and it is wonderful. Each language is different. Each can teach you something new and change how you approach programming. I wrote very different code in Java than in Objective-C. It changed again when I first touched Swift. Each language left its mark on me. Learn different programming languages, embrace them, and stay open. Don't be afraid to learn something. [[00:04:50]](https://youtube.com/watch?v=suATPK45sjk_transcript&t=290s)

### Languages

For example, a very common question from people learning Kotlin is: do I have to learn Java? I think it's not the best way to put it. Will learning Java make you a better Kotlin developer? Yes, definitely. You'll better understand the APIs of libraries you'll probably want to use. You'll understand how the whole environment works. You'll understand why some things in Kotlin are the way they are. Don't be afraid to learn something that isn't strictly necessary. [[00:06:19]](https://youtube.com/watch?v=suATPK45sjk_transcript&t=379s)

#### Working with people

As we advance our careers as engineers—whether you're a consultant engineer or a product engineer—you'll be working with people more and more inevitably. You'll be reading requirements, stories, comments. You'll be writing them. You'll be speaking, communicating, explaining, presenting. You work with people a lot, sometimes more than you work with code, especially if you measure your time in minutes per day. The best engineers are also great at working with people in everything that entails. [[00:07:00]](https://youtube.com/watch?v=suATPK45sjk_transcript&t=420s)

### Don't stick to one career

Don't stick to one career. You're not doomed to be a software developer for your whole life. Take me as an example. I learned to be an information security specialist, then became an Android developer, switched to iOS development, became a team lead, did some backend development, then became a manager and a product manager. Now I'm leading the development of a programming language. That's actually great because in each role, you learn different skills that may help you in the main one if you decide to return. If you become a product manager, you'll be much better at understanding what, why, and for whom you're building—it drastically helps you become a staff-plus engineer. You won't just write code; you'll think about business needs. If you become a team lead and then decide to stop, it teaches you essential skills like managing your time and other people's time, or how to make decisions in uncertainty. Don't stick to one career. Your life is long. You can try different things and find what suits you best. [[00:07:44]](https://youtube.com/watch?v=suATPK45sjk_transcript&t=464s)

#### Work-life balance

When you're young, it feels like you can work twenty hours a day or eighteen hours a day, and it's fun to write software. You may end up with your day job and your hobby project—working eight hours on one thing and then another eight hours on the second thing. That's fun, and I did some of that when I was younger. But it's very important to not focus only on that, not to ignore other things—other fun ways to spend time, other ways to take care of your body, your emotional state, your mind. Read things, go for a walk, do physical activities. Finding a healthy balance between all of these allows you to sustain your productivity and sustain the joy that software development brings you for a much longer time. [[00:09:10]](https://youtube.com/watch?v=suATPK45sjk_transcript&t=550s)

#### Keep learning and aim higher

Keep learning new things. Go deeper, go wider. Look at how things are done nowadays. If there's a new big trend, look into it. Nowadays it's generative AI—look into that. It helps you stay up to date, helps you be a better engineer. Also, aim higher in general. A lot of people underestimate themselves and don't try things they could have succeeded at. You should try. Experiment with things that feel out of reach. Apply to jobs you think you're not good enough for. Prepare for those interviews and get the job. That's the top piece of advice I can give. [[00:10:06]](https://youtube.com/watch?v=suATPK45sjk_transcript&t=606s)

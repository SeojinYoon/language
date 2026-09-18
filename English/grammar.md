

# Correlative conjunction

다음과 같은 종류를 가짐
- both A and B
- neither A nor B
- either A or B
- not only A but also B
- not A but B
- whether A or B

## Intition

## Background

## Property

$$
\begin{array}{cccc}
\hline
\text{\textbf{상관접속사}} & \text{\textbf{집합 표현}} & \text{\textbf{명제 논리}} & \text{\textbf{논리 게이트}} \\
\hline
\text{Both } A \text{ and } B & A \cap B & A \land B & \text{AND} \\
\text{Neither } A \text{ nor } B & (A \cup B)^c & \neg (A \lor B) & \text{NOR} \\
\text{Either } A \text{ or } B \text{ (Inc.)} & A \cup B & A \lor B & \text{OR} \\
\text{Either } A \text{ or } B \text{ (Exc.)} & A \mathbin{\triangle} B & A \oplus B & \text{XOR} \\
\text{Not } A \text{ but } B & B \setminus A & \neg A \land B & B \land \neg A \\
\text{Not only } A \text{ but also } B & A \cap B & A \land B & \text{AND} \\
\text{Whether } A \text{ or not} & A \cup A^c = \mathcal{U} & A \lor \neg A \equiv \top & \text{Tautology} \\
\hline
\end{array}
$$

### Either - Inclusive(Inc.), Exclusive(Exc.)

- 상황 자체가 겹칠 수 없는 경우 $\rightarrow$ Exclusive
    > The light is either on or off
- 둘 다 겹쳐도 좋은 경우 $\rightarrow$ Inclusive
    > If you have either a pen or a pencil, please write this down
    
## Example

## Application

